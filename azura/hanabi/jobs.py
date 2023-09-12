from ..mvc.discord.models import User
from ..mvc.music.models import Playlist
from .objects import EnqueueMode
from .utils import generate_loading_bar

import abc
import asyncio
import hikari
import random


class EnqueueJob(abc.ABC):
    """
    Defines the concept of an EnqueueJob.

    When enqueueing takes place, we have to interrupt
    the access of certain parts of the session, namely the queue.
    This is no different from other commands, but the difference with
    enqueueing is that it can take a long time. We can't hold the 
    session lock for that long because it would prevent other
    commands from going through, so to mitigate this, we create
    jobs.

    An EnqueueJob specifically is an abstract concept from which
    the different kinds of enqueueing precipitate, and which allows
    extensibility.

    session: LocalSession - The hanabi LocalSession to which this job belongs.
    requester: int - The UID of the author of the enqueue command.
    playlist: Playlist - an ORM playlist to enqueue.
    shuffle: bool - Whether or not the playlist should be shuffled before enqueueing.
    enqueue_delay: float - How long to wait between each track. Low values can cause API problems.
    """
    def __init__(
            self,
            session, 
            requester: int,
            playlist: Playlist,
            shuffle: bool,
            enqueue_delay: float = 0.1
        ):
        self.session = session
        self.requester = requester
        self.playlist = playlist
        self.shuffle = shuffle
        self.enqueue_delay = enqueue_delay

        self._message = None
        self._done = 0
        self._total = None
        self._in_progress = False
        self._cancel = False
        self._failed_tracks = []
    
    @abc.abstractmethod
    def _pos_algorithm(self, iteration: int) -> int:
        """
        The position algorithm takes in the current iteration we're on when
        enqueueing tracks, and returns a position at which the current track
        will be inserted in the queue.
        """
        ...
    
    @abc.abstractproperty
    def mode(self) -> EnqueueMode:
        """
        Each subclass must define the EnqueueMode it's responsible
        for via the enum.
        """
        ...
    
    @property
    def _progress(self) -> float:
        """Returns the current progress of enqueueing."""
        return self._done / self._total

    def cancel(self):
        """Function cancels the job."""
        self._cancel = True

    def get_embed(self):
        """Generate the embed to be sent to the user based on the current state."""
        plural = "track" if self._total == 1 else "tracks"
        verb = "Enqueued" if self._in_progress is False else "Enqueueing"
        if self._cancel is True:
            title = "Enqueueing was cancelled"
        else:
            verb = "Enqueueing" if self._in_progress is True else  "Enqueued"
            title = f"{verb} in {self.mode.value} mode"
        progress_bar = generate_loading_bar(self._progress)
        embed = hikari.Embed(
            title=title,
            description=f"{self._total} {plural} from {self.playlist.name}\n\n`{self._done} {progress_bar} {self._total}`"
        )
        failed = "\n".join([entry.title for entry in self._failed_tracks])
        if failed:
            embed.add_field(name="Failed Tracks", value=failed)
        
        if self._in_progress is False and self._cancel is False:
            embed.set_thumbnail("https://www.nicepng.com/png/full/332-3325750_check-395x340-green-circle-check-mark.png")
        elif self._in_progress is False and self._cancel is True:
            embed.set_thumbnail("https://creazilla-store.fra1.digitaloceanspaces.com/cliparts/5626337/red-x-clipart-md.png")
        return embed
    
    async def __call__(self):
        """
        Defines the overall behavior of an Enqueuejob.

        This is what is ultimately passed to the event loop
        when the job is started in the LocalSession. When one
        EnqueueJob is running, a lock is acquired which prevents
        any other jobs from beginning or running while this one is.
        This is to prevent tracks from flying all over the place.
        """
        # Acquire lock to prevent other jobs from starting.
        async with self.session.enqueue_lock:
            # Obtain all entries from the playlist, shuffle if needed.
            entries = await self.playlist.get_entries()

            if not entries:
                self._in_progress = False
                await self.session.send(f"The requested playlist `{self.playlist.name}`, does not have any entries.")
                return

            if self.shuffle is True:
                random.shuffle(entries)
            
            self._total = len(entries)
            self._in_progress = True

            # Begin the message update task
            self.session.hanabi.loop.create_task(self.message_task())

            # Iterate through all entries
            for i, entry in enumerate(entries):

                # If the cancel flag is set, stop dead
                if self._cancel is True:
                    self._in_progress = False
                    return

                # To actually modify the queue safely, we need to acquire the
                # session lock itself, but we don't want to do it for so long
                # that other commands can't run.
                async with self.session.lock:
                    # Load the track in from Hanabi
                    track = await self.session.hanabi.load_or_search_tracks(entry.source)
                    if isinstance(track, list):
                        # This is used if the source isn't a direct link.
                        # In which case, results are returned, and we take the first one.
                        track = track[0]
                    
                    # If track is null at this point, it means that for one reason
                    # or another, loading the track failed. So we add it to a list
                    # which can be used to inform the requester, and move on.
                    if track is None:
                        self._failed_tracks.append(entry)
                        self._done = i + 1
                        await asyncio.sleep(self.enqueue_delay)
                        entry.failed = True
                        await entry.asave()
                        continue
                    
                    # Set the requester of the track
                    track.requester = self.requester
                    track.begin_at = entry.start_ms
                    track.end_at = entry.end_ms
                    
                    # Obtain the position from the algorithm. This will vary
                    # depending on which subclass is actually in use. 
                    pos = self._pos_algorithm(i)
                    # Insert the track at that position.
                    self.session.dinsert(track, pos)

                    # Finally, if the session is not playing, begin playback.
                    if self.session._is_playing is False:
                        user, _ = await User.objects.aget_or_create(id=self.requester)
                        self.session._volume = user.volume
                        await self.session._play()
                    # Record progress.
                    self._done = i + 1
                    await asyncio.sleep(self.enqueue_delay)

        # Set flag to finalize enqueueing.
        self._in_progress = False
    
    async def message_task(self):
        """
        This task is started separate to the EnqueueJob itself.
        Its purpose is to send and update a message while enqueueing
        is taking place in order to show progress and display errors.
        """
        while self._in_progress is True:
            if self._message is None:
                self._message = await self.session.send(embed=self.get_embed())
            else:
                await self._message.edit(content=self.get_embed())
            await asyncio.sleep(2)
        
        self._message = await self._message.edit(content=self.get_embed())
        self.session._jobs.remove(self)
        

class FIFOJob(EnqueueJob):
    """
    Define the behavior of FIFO enqueueing.

    playlist = [a, b, c]
       queue = [1, 2, 3]

                          a  b  c
                          v  v  v
    new_queue = [1, 2, 3, a, b, c]
    """
    mode = EnqueueMode.FIFO

    def _pos_algorithm(self, iteration: int) -> int:
        return len(self.session._queue)


class LIFOJob(EnqueueJob):
    """
    Define the behavior of LIFO enqueueing.

    playlist  = [a, b, c]
       queue  = [1, 2, 3]

                 a  b  c
                 v  v  v
    new_queue = [a, b, c, 1, 2, 3]
    """
    mode = EnqueueMode.LIFO

    def _pos_algorithm(self, iteration: int) -> int:
        return self.session._pos + 1


class RandomJob(EnqueueJob):
    """
    Define the behavior of RANDOM enqueueing.

    playlist  = [a, b, c]
       queue  = [1, 2, 3]

                   c         a  b
                   v         v  v
    new_queue = [1, c, 2, 3, a, b]
    (Actual results vary, it's random.)
    """
    mode = EnqueueMode.RANDOM

    def _pos_algorithm(self, iteration: int) -> int:
        if self.session.dis_empty():
            return 0
        return random.randint(self.session._pos+1, len(self.session._queue))


class InterlaceJob(EnqueueJob):
    """
    Define the behavior of INTERLACE enqueueing.

    playlist  = [a, b, c]
       queue  = [1, 2, 3]

                    a     b     c
                    v     v     v
    new_queue = [1, a, 2, b, 3, c]
    """
    mode = EnqueueMode.INTERLACE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._factor = None

    def _pos_algorithm(self, iteration: int) -> int:
        return ((iteration * self.factor) + self.factor) + self.session._pos

    @property
    def factor(self):
        if self._factor is None:
            unique = self.session.dget_unique_requesters()
            if self.requester in unique:
                unique.remove(self.requester)
            self._factor = len(unique) + 1
        return self._factor


def create_enqueue_job(session, requester: int, playlist: Playlist, mode: EnqueueMode, shuffle: bool, enqueue_delay: float = 0.1):
    if mode == EnqueueMode.FIFO:
        return FIFOJob(session, requester, playlist, shuffle, enqueue_delay=enqueue_delay)
    elif mode == EnqueueMode.LIFO:
        return LIFOJob(session, requester, playlist, shuffle, enqueue_delay=enqueue_delay)
    elif mode == EnqueueMode.RANDOM:
        return RandomJob(session, requester, playlist, shuffle, enqueue_delay=enqueue_delay)
    elif mode == EnqueueMode.INTERLACE:
        return InterlaceJob(session, requester, playlist, shuffle, enqueue_delay=enqueue_delay)