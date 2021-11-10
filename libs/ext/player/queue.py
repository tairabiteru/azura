"""Module handles the playback queue, and its related items."""

from libs.core.conf import conf
from libs.ext.player.errors import QueueIsEmpty, EndOfQueue
from libs.ext.player.track import Track
from libs.ext.utils import ms_as_ts, progressBar, url_is_valid
from libs.orm.songdata import GlobalSongData
from libs.orm.playlist import PlaylistEntry

import asyncio
import discord
from enum import Enum
import random
import wavelink


class Repeat(Enum):
    """Enum defining repeat modes."""

    NONE = 0
    ONE = 1
    ALL = 2


class Queue:
    """
    Define a playback queue.

    The queue used here is nothing more than a carefully controlled list.
    We can get away with this by not removing things from the list, but rather
    by modifying a position variable which denotes the "front" of the queue.
    Modification of this variable must be carefully monitored, as this is where
    the majority of threading issues will come frome.
    """

    def __init__(self):
        """Initialize queue."""
        self._queue = []
        self.position = 0
        self.repeat_mode = Repeat.NONE

    @property
    def empty(self):
        """Tell whether or not the queue is empty."""
        return not self._queue

    @property
    def current_track(self):
        """Retrieve the current track from the queue. Raise exception if empty."""
        if self.empty:
            raise QueueIsEmpty

        if self.position <= len(self._queue) - 1:
            return self._queue[self.position]

        print(f"From CT: {self.position}")
        print(list([track.title for track in self._queue]))
        raise EndOfQueue

    def info_embed(self, bot):
        """
        Generate the information embed.

        This is used during playback to create the information message, which
        contains information about the current track being played.
        Truth be told, I don't know why I put this in the Queue. Maybe I had
        a reason when I did it, but I might move it into the Player in the
        future.
        """
        ct = self.current_track
        sde = GlobalSongData.obtain(entry=ct)
        embed = discord.Embed(title=ct.title, colour=discord.Colour(0x14ff), url=f"{ct.uri}")
        _ = embed.set_image(url=ct.thumb) if ct.thumb else None
        embed.add_field(name="Duration", value="{}".format(ms_as_ts(ct.length)))
        live = "Yes" if ct.is_stream else "No"
        embed.add_field(name="Author", value=f"{ct.author}")
        embed.add_field(name="Video ID", value=f"{ct.ytid}")
        embed.add_field(name="Global Plays", value=f"{sde.global_plays}")
        embed.add_field(name="Plays by Requester", value=f"{sde.plays_by(uid=ct.requester.id)}")
        embed.add_field(name="Requester", value=ct.requester.name)
        embed.add_field(name="Live Stream", value=live)
        return embed

    @property
    def next_tracks(self):
        """Obtain all upcoming tracks."""
        if self.empty:
            raise QueueIsEmpty

        return self._queue[self.position + 1:]

    @property
    def past_tracks(self):
        """Obtain all previous tracks."""
        if self.empty:
            raise QueueIsEmpty

        return self._queue[:self.position]

    @property
    def length(self):
        """Get length of queue. Note this includes ALL songs, past and future."""
        return len(self._queue)

    def add_fifo(self, *args):
        """Add to queue in FIFO mode. (to the back)"""
        self._queue.extend(args)

    def add_lifo(self, track):
        """Add to queue in LIFO mode. (to the front)"""
        self._queue.insert(self.position+1, track)

    def add_random(self, track):
        """Add to the queue in RANDOM mode."""
        self._queue.insert(random.randint(self.position+1, self.length-1), track)

    def add_interlace(self, track, pos, factor):
        """Add to the queue in INTERLACE mode."""
        position = (pos * factor) + factor
        position = position + self.position
        self._queue.insert(position, track)

    def remove_track(self, id):
        self._queue = list([track for track in self._queue if track.id != id])

    def get_next_track(self):
        """Obtain the next track from the queue and advances the position."""
        if not self._queue:
            raise QueueIsEmpty

        self.position += 1

        if self.position < 0:
            return None
        elif self.position > len(self._queue) - 1:
            if self.repeat_mode == Repeat.ALL:
                self.position = 0
            else:
                return None

        return self._queue[self.position]

    def shuffle(self):
        """
        Shuffle the queue in place.

        This is more of a convenience function, but as far as I remember, I
        haven't used it anywhere.
        """
        if self.empty:
            raise QueueIsEmpty

        upcoming = self.next_tracks
        random.shuffle(upcoming)
        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)

    def set_repeat_mode(self, mode):
        """Set the repeat mode of the queue."""
        if mode == "none":
            self.repeat_mode = Repeat.NONE
        elif mode == "one":
            self.repeat_mode = Repeat.ONE
        elif mode == "all":
            self.repeat_mode = Repeat.ALL

    def clear(self):
        """Clear the queue, reset position to 0."""
        self._queue.clear()
        self.position = 0


class EnqueueJob:
    """
    Define an enqueueing job.

    These are objects which essentially define an enqueueing instruction based
    on the original arguments sent in the command. They define the embed for the
    job, as well as the specific process required to enqueue the requested songs.

    Funnelling all instructions through this class plays a large role in how Azura
    can handle multiple enqueueing requests at a time while also playing songs
    without compromising thread safety. Specific flags are set whenever an
    enqueueing job is executed that informs the main music-playing thread that
    it must wait to switch songs, or vice versa.
    """
    def __init__(self, ctx, wl, name, playlist, mode="FIFO"):
        """Initialize an EnqueueJob."""
        self.name = name
        self.ctx = ctx
        self.wl = wl
        self.playlist = playlist
        self.mode = mode
        self.pos = 0
        self._cancel = asyncio.Event()

    def cancel(self):
        self._cancel.set()

    @property
    def embed(self):
        """Define the embed for an EnqueueJob."""
        if self.pos == len(self.playlist):
            status = f"Enqueued '{self.name}' in {self.mode} Mode"
        else:
            status = f"Enqueueing '{self.name}' in {self.mode} Mode"

        eBar = progressBar(self.pos, len(self.playlist))
        desc = f"`{self.pos} {eBar} {len(self.playlist)}`"
        embed = discord.Embed(title=status, description=desc, colour=discord.Colour(0x14ff))
        embed.add_field(name="Requester", value=self.ctx.author.name)

        if self.failures:
            embed.add_field(name="Failures", value=", ".join(self.failures))

        if self.pos / len(self.playlist) == 1:
            embed.add_field(name="Progress", value="Done")
        else:
            embed.add_field(name="Progress", value=f"{int(round((float(self.pos) / len(self.playlist)) * 100, 0))}%")

        return embed

    async def execute(self, player):
        """
        Execute the enqueue job.

        This defines the core instructions executed by the bot whenever a playlist
        or song is enqueued. Tracks are enqueued step-wise, which allows the
        enqueueing thread to pause for things like switching songs to maintain
        thread safety.
        """
        successes = []
        self.failures = []

        factor = []
        try:
            for track in player.queue.next_tracks:
                if track.requester.id not in factor:
                    factor.append(track.requester.id)
        except QueueIsEmpty:
            pass
        if self.ctx.author.id not in factor:
            factor.append(self.ctx.author.id)
        factor = len(factor)
        if factor == 1:
            factor = 2

        if player.enqmsg is None:
            player.enqmsg = await self.ctx.send(embed=self.embed)

        for i, entry in enumerate(self.playlist):
            # Check for cancellation
            if self._cancel.is_set():
                return

            # Wait for the all clear from the playing thread
            await player.enq_all_clear.wait()

            # If clear, inform the playing thread that it is NOT clear
            player.adv_all_clear.clear()

            # A single song is enqueued below. At this point, this MUST complete
            # before the playing thread may advance songs.
            self.pos += 1
            if isinstance(entry, PlaylistEntry):
                query = entry.generator
                start = entry.start
                end = entry.end
            else:
                query = entry
                start = 0
                end = -1

            if isinstance(entry, wavelink.Track):
                tracks = [entry]
            else:
                if not url_is_valid(query):
                    query = f"ytsearch:{query}"
                tracks = await self.wl.get_tracks(query)

            if not tracks:
                if isinstance(entry, PlaylistEntry):
                    name = entry.custom_title if entry.custom_title else entry.generator
                else:
                    name = query
                self.failures.append(name)
                continue

            track = Track(tracks[0], ctx=self.ctx, requester=self.ctx.author, start=start, end=end)
            if self.mode.upper() == "FIFO":
                player.queue.add_fifo(track)
            elif self.mode.upper() == "LIFO":
                player.queue.add_lifo(track)
            elif self.mode.upper() == "INTERLACE":
                player.queue.add_interlace(track, i, factor)
            elif self.mode.upper() == "RANDOM":
                player.queue.add_random(track)
            successes.append(track)

            try:
                last3 = await self.ctx.history(limit=3).flatten()
                if player.enqmsg.id not in [msg.id for msg in last3]:
                    await player.enqmsg.delete()
                    player.enqmsg = await self.ctx.send(embed=self.embed)
                else:
                    await player.enqmsg.edit(embed=self.embed)
            except AttributeError:
                player.enqmsg = await self.ctx.send(embed=self.embed)
            await asyncio.sleep(conf.music.enqueueingShotDelay)

            # Start playback if necessary.
            if not player.is_playing and (player.queue.length == 1 or player.queue.length == player.queue.position + 1):
                await player.start_playback()

            # Set the all-clear for the playing thread.
            # At this point, if the playing thread needs to advance tracks,
            # it can and will, causing this thread to halt above at line 249.
            player.adv_all_clear.set()


class DequeueJob:
    """
    Define a DequeueJob.

    A DequeueJob is basically the same thing as an EnqueueJob, only it functions
    differently. An EnqueueJob iterates over
    """
    def __init__(self, ctx, wl, player, member):
        self.ctx = ctx
        self.wl = wl
        self.player = player
        self.member = member
        self.pos = 0
        self._cancel = asyncio.Event()

        if self.member is None:
            self.ids = []
            initial_voice_ids = list([member.id for member in self.ctx.author.voice.channel.members])
            for track in self.player.queue._queue:
                if track.requester.id not in initial_voice_ids:
                    self.ids.append(track.requester.id)
        else:
            self.ids = [self.member.id]

    def cancel(self):
        self._cancel.set()

    @property
    def embed(self):
        if self.pos == self.init_pos:
            status = "Dequeued songs"
        else:
            status = "Dequeueing songs"
        dBar = progressBar(self.pos, self.init_pos)
        desc = f"`{self.pos}` {dBar} {self.init_pos}"
        embed = discord.Embed(title=status, description=desc, colour=discord.Colour(0x14ff))
        embed.add_field(name="Requester", value=self.ctx.author.name)

        if self.pos / self.init_pos == 1:
            embed.add_field(name="Progress", value="Done")
        else:
            embed.add_field(name="Progress", value=f"{int(round((float(self.pos) / self.init_pos) * 100, 0))}%")
        return embed

    async def execute(self, player):
        self.init_pos = len(self.player.queue.next_tracks)
        for track in player.queue.next_tracks:
            if self._cancel.is_set():
                return

            await player.enq_all_clear.wait()
            player.adv_all_clear.clear()

            self.pos += 1

            if track.requester.id in self.ids:
                player.queue.remove_track(track.id)

            try:
                last3 = await self.ctx.history(limit=3).flatten()
                if player.enqmsg.id not in [msg.id for msg in last3]:
                    await player.enqmsg.delete()
                    player.enqmsg = await self.ctx.send(embed=self.embed)
                else:
                    await player.enqmsg.edit(embed=self.embed)
            except AttributeError:
                player.enqmsg = await self.ctx.send(embed=self.embed)

            player.adv_all_clear.set()
