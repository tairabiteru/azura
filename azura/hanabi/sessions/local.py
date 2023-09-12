from .base import BaseSession
from ..objects import Track, RepeatMode, EnqueueMode
from ..queue import Queue, InvalidPosition
from ..embeds import PlayerEmbed, update_player_embed
from ..jobs import create_enqueue_job
from ...mvc.discord.models import User
from ...mvc.music.models import Playlist, PlaybackHistoryEntry

import asyncio
import hikari
import time
import typing


class LocalSession(BaseSession, Queue):
    def __init__(self, hanabi, guild_id: int, voice_id: int, channel_id: int):
        """
        Represents a voice session "local" to the possessing bot.

        A LocalSession is arguably at the core of Hanabi. It's responsible
        for all of the actions performed by and buttons, and it's the most
        direct way Hanabi interfaces with the bot. While a RemoteSession
        can also be minted by Hanabi, that RemoteSession will ultimately be
        linked to a LocalSession on the bot that has control over the
        session. Because of this, a LocalSession is probably the most
        complicated part of Hanabi.

        Similar to Queue, the methods here are highly controlled by asyncio.Locks,
        and many methods have "d" parallels which are to be considered "dangerous."
        That is, they shouldn't be executed without acquiring the requisite lock.

        self.enqueue_lock: asyncio.Lock - A lock to be acquired whenever making
            mass alterations to the queue.
        self.enqueue_embed: Optional[EnqueueEmbed] - A special embed class designed
            to manage the various tasks related to enqueueing.
        self._repeat_mode: RepeatMode - Enum responsible for the current repeat mode.
        self._state: Optional[PlayerState] - Information from Lavalink related to
            playback, like the position for example.
        self._is_playing: bool - True if the player is playing, False otherwise.
        self._current_track: Optional[Track] - The current playing track from Lavalink.
        self._is_paused: bool - True if paused, False if not.
        self._volume: int - The current player's volume.
        self._last_player_update: int - The last UNIX timestamp when the player updated.
            This is mainly used to determine whether or not to update the player message
            as sometimes player updates fire too quickly for the API.
        self._last_track_completion: Optional[int] - The UNIX timestamp when the last
            track completed.
        self._last_pos: Optional[int] - The last position of the queue which played.
        self._jobs: List[EnqueueJob] - A list of currently running enqueueing jobs.
        self._player_embed: Optional[PlayerEmbed] - An embedish object managing the player
            message and its tasks.
        """
        BaseSession.__init__(self, hanabi, guild_id, voice_id, channel_id)
        Queue.__init__(self)

        self.enqueue_lock = asyncio.Lock()
        self.enqueue_embed = None

        self._repeat_mode: RepeatMode = RepeatMode.NONE
        self._state = None
        self._is_playing: bool = False
        self._current_track = None
        self._is_paused = False
        self._volume = 100
        self._last_player_update = 0
        self._last_track_completion = None
        self._last_pos = None
        self._jobs = []
        self._player_embed = None

    async def _play(
            self,
            track: Track = None,
            requester: typing.Optional[int] = None,
            replace: bool = False,
            start_playing_if_not: bool = True,
            enqueue: bool = True,
            position=None
        ):
        """
        Command for controlling playback.

        By default, if this command is called with a no arguments,
        the track at the current queue position will be played.

        If the track parameter is passed, then the player will begin
        playing that track if the player is not currently playing anything.
        If it is, the track will instead be enqueued in FIFO mode.

        track: Optional[Track] - The track to play or enqueue.
        requester: Optional[int] - The UID of the person who requested playback.
        replace: bool - If true, the currently playing track will be immediately
            stopped and replaced with the track passed.
        start_playing_if_not: bool - If the player is not currently playing, 
        and this is true, playback will begin automatically.
        enqueue: bool - If true, the track will be placed at the end of the queue.
        position: Optional[int] - The position at which to enqueue the track, if any.
        """
        if track is not None:
            track.requester = requester

        if self.dis_empty() is True:
            if track is None:
                raise ValueError("play() may not be called with no kwargs if the queue is empty.")
            self.dappend(track)
        else:
            if track is None:
                track = self.dget_current()
            else:
                if enqueue is True:
                    self.dappend(track)
                elif position is not None:
                    self.insert(track, position-1)
                else:
                    self.dinsert_after_current(track)
                if self._is_playing is False:
                    self.dadvance()
        
        if replace is True or (start_playing_if_not is True and self._is_playing is False):
            await self.hanabi.update_player(
                self.guild_id,
                data = {
                    'encodedTrack': track.encoded,
                    'position': track.begin_at,
                    'volume': self._volume
                }
            )
    
    async def play_cmd(self, title: str, requester: int, position: typing.Optional[int] = None):
        """
        Implements the behavior of the play command.

        This command mirrors RemoteSession.play_cmd.
        """
        async with self.lock:
            track = await self.hanabi.load_or_search_tracks(title)
            if isinstance(track, list):
                track = track[0]

            if position is not None:
                position -= 1
            
            if self._is_playing is False:
                user, _ = await User.objects.aget_or_create(id=requester)
                self._volume = user.volume
            await self._play(track=track, requester=requester, position=position)
    
    async def disconnect(self):
        """
        Disconnect from voice and clean up.

        This method shouldn't really be called by itself, and is only
        properly invoked within Hanabi. While this will cause the bot
        to disconnect and clean up the session's variables, it does
        not actually destroy the session object itself within Hanabi.
        """
        await self.hanabi.bot.update_voice_state(self.guild_id, None)
        for job in self._jobs:
            job.cancel()
        if self._player_embed is not None:
            await self._player_embed.stop()

    async def dclear(self):
        """Resets the queue and stops playback."""
        self.reset()
        await self.hanabi.update_player(
            self.guild_id,
            data = {
                "encodedTrack": None
            }
        )

    async def dpause(self, state):
        """Dangerous version of pause()."""
        await self.hanabi.update_player(
                self.guild_id,
                data = {
                    "paused": state
                }
            )
        self._is_paused = state
        return state
    
    async def pause(self, state):
        """Pauses the player."""
        async with self.lock:
            return await self.dpause(state)
    
    async def pause_cmd(self, state):
        """
        Handles the pause command.

        The command operates a little differently because we need to inform
        the requester of this via send().
        """
        async with self.lock:
            if self._current_track is None:
                return await self.send("I'm not playing anything right now.", delete_after=10)
            
            if self._is_paused == state:
                verb = "is already paused" if self._is_paused is True else "isn't paused"
                return await self.send(f"Playback {verb}.", delete_after=10)

            await self.dpause(state)
            verb = "paused" if state is True else "resumed"
            await self.send(f"Playback has been {verb}.", delete_after=10)
    
    async def seek(self, position):
        """Seeks the player to a position in ms."""
        await self.hanabi.update_player(
            self.guild_id,
            data = {
                "position": position
            }
        )
    
    @update_player_embed("post-call")
    async def dvolume(self, requester: int, volume: int):
        """Dangerous version of volume"""
        await self.hanabi.update_player(
            self.guild_id,
            data = {
                "volume": volume
            }
        )
        self._volume = volume
        user, _ = await User.objects.aget_or_create(id=requester)
        user.volume = volume
        await user.asave()
    
    async def volume(self, requester: int, volume: int):
        """Sets the volume of the player."""
        async with self.lock:
            return await self.dvolume(requester, volume)
    
    async def volume_cmd(self, requester: int, setting: str):
        """
        Command to set the volume of the player.

        Once again, operates a little differently since we need
        to inform the user of these changes.
        """
        async with self.lock:
            try:
                if setting.startswith("+"):
                    new_volume = self._volume + int(setting[1:])
                    verb = "increased"
                elif setting.startswith("-"):
                    new_volume = self._volume - int(setting[1:])
                    verb = "decreased"
                else:
                    new_volume = int(setting)
                    verb = "set"
            except ValueError:
                return await self.send(f"The setting `{setting}` is not valid.", delete_after=30)
            
            if not (0 <= new_volume <= 100):
                return await self.send(f"The resulting volume must be between 0 and 100. The setting `{setting}` causes it to be out of bounds.", delete_after=30)

            await self.dvolume(requester, new_volume)
            await self.send(f"Volume {verb} to `{new_volume}%`")

    async def enqueue_cmd(self, name: str, owner: int, requester: int, shuffle: bool = False, mode: EnqueueMode = EnqueueMode.FIFO, bypass_owner: bool = False):
        """
        Handles enqueue requests.

        An enqueue request happens when one invokes the /enqueue command,
        I.E, they're enqueueing a playlist. Playlists have to be handled
        differently from normal play requests because they cause mass
        alteration of the queue, but also take a while. The play command
        does this by acquiring the session lock, but since enqueue requests
        can take many seconds, this would stop the execution of all further
        commands until it completes.

        Instead, the enqueue command makes use of an EnqueueJob object,
        which is described elsewhere.
        """
        owner, _ = await User.objects.aget_or_create(id=owner)
        try:
            playlist = await Playlist.objects.aget(owner=owner, name=name)
        except Playlist.DoesNotExist:
            owner.attach_bot(self.hanabi.bot)
            await owner.aresolve_all()
            return await self.send(f"A playlist owned by `{owner.obj.username}` named `{name}` does not exist.")
        
        if playlist.is_public is False and owner.id != requester and bypass_owner is False:
            return await self.send("The requested playlist is not owned by you and has not been made public by its owner.")
        
        job = create_enqueue_job(self, requester, playlist, mode, shuffle)
        self._jobs.append(job)
        self.hanabi.loop.create_task(job())
    
    async def dequeue_cmd(self, positions: typing.Optional[typing.List[int]] = None, requester: typing.Optional[int] = None):
        """
        Dequeue command.

        Dequeuing is obviously the opposite of enqueueing. Unlike
        enqueuing though, we don't need to define special jobs for
        it, nor do we need to be as concerned with the session lock.

        Enqueueing involves the use of many REST API calls to Lavalink,
        while enqueueing simply involves alteration of the existing queue.
        Because of this, the queue can and is altered all in one fell swoop.
        """
        # Acquire the enqueueing lock. Dequeueing cannot take place
        # during an ongoing enqueueing/dequeuing process.
        async with self.enqueue_lock:
            # List to store successfully dequeued tracks.
            dequeued = []

            # If dequeueing by positions...
            if positions:
                # Acquire the session lock
                async with self.lock:
                    # If the queue is empty, we can't dequeue anything.
                    if len(self._queue) == 0:
                        return await self.send("The queue is currently empty.", delete_after=30)

                    # Otherwise, iterate through all specified positions
                    for position in positions:
                        try:
                            # Try to dequeue the track at each position
                            # We subtract what's been dequeued so far because
                            # the positions change over time.
                            track = self.dremove_at(position-len(dequeued))
                            dequeued.append(track)
                        except InvalidPosition as e:
                            # If InvalidPosition is raised, inform the user that
                            # the specified position wasn't valid.
                            await self.send(str(e), delete_after=10)
            
            # If dequeueing by requester...
            if requester:
                # Acquire the session lock
                async with self.lock:
                    # Also check for empty queue
                    if len(self._queue) == 0:
                        return await self.send("The queue is currently empty.", delete_after=30)
                    
                    # Begin at position 1
                    i = 1
                    # Iterate while the current position is less than or equal to the queue's length.
                    # Once again we do this because the length of the queue is changing dynamically.
                    while i-len(dequeued) <= len(self._queue):
                        # Check at each position if the requester matches
                        if self._queue[i-len(dequeued)-1].requester == requester:
                            try:
                                # If it is, attempt to remove the track at that position.
                                track = self.dremove_at(i-len(dequeued))
                                dequeued.append(track)
                            except InvalidPosition:
                                # If InvalidPosition is raised, this can only be because
                                # it's the current track. We don't need to inform the user of this now.
                                pass
                        # Increment i
                        i += 1
                    
                # If no tracks were dequeued, inform the requester.
                if len(dequeued) == 0:
                    user = self.hanabi.bot.cache.get_user(requester)
                    return await self.send(f"None of the tracks which are able to be dequeued right now were requested by {user.username}.", delete_after=30)

            # Finally, for either process, inform the user of the results.
            plural = "track" if len(dequeued) == 1 else "tracks"
            await self.send(f"Dequeued {len(dequeued)} {plural}.")
    
    async def skip(self, by: typing.Optional[int]=None, to: typing.Optional[int]=None, button: bool=False):
        """
        Skip command.

        This command can take one of two parameters, 'by' or 'to':

        If by is passed, the queue will be advanced by the amount requested.
        For example, if the queue is currently at the second position, and
        skip(by=3) is called, the queue will be advanced to position 5,
        assuming it exists. This also works with negative numbers.

        If to is passed, the queue is instead advanced directly to the
        requested position. For example, if the queue is currently at the
        second position and skip(to=7) is called, the queue will be advanced
        to position 7, assuming it exists.

        The button parameter simply tells whether or not this is being called
        by a button press or not. The actions we take are largely the same if so,
        but the phrasing of the responses is slightly different.
        """
        async with self.lock:
            try:
                if by:
                    track = self.dadvance_by(by)
                    v, a = "by", by
                if to:
                    track = self.dadvance_to(to)
                    v, a = "to position", to
            except InvalidPosition as e:
                if button is True:
                    if by == -1:
                        return await self.send("You have reached the beginning of the queue.")
                    else:
                        return await self.send("You have reached the end of the queue.")
                return await self.send(str(e), delete_after=30)
            
            user, _ = await User.objects.aget_or_create(id=track.requester)
            self._volume = user.volume
            await self._play(replace=True)
        await self.send(f"Advanced the queue {v} `{a}`.", delete_after=30)
    
    async def set_repeat_mode(self, mode: RepeatMode):
        """Sets the repeat mode."""
        async with self.lock:
            self._repeat_mode = mode
    
    async def display_queue(self, amount=10):
        """
        Command to display the current queue.

        This is the method invoked by the /queue command.
        """
        async with self.lock:
            embed = hikari.Embed(title="Current Queue")
            contents = self.dget_contents(amount=amount)
            if not contents:
                embed.description = "```The queue is empty.```"
            else:
                embed.description = f"```{contents}```"
            await self.send(embed=embed, delete_after=60)

    async def on_track_start(self, event):
        """Callback for TrackStart event."""
        # Acquire the session lock to prevent stupid
        async with self.lock:
            # Update is_playing and the current track
            self._is_playing = True
            self._current_track = event.track

            # Generate a new player embed with the new track and
            # start the embed management task.
            self._player_embed = PlayerEmbed(self)
            await self._player_embed.begin()

            # Set the last position
            self._last_pos = self._pos

            # Handle the creation of PlaybackHistoryEntry
            requester, _ = await User.objects.aget_or_create(id=self.dget_current().requester)
            entry = PlaybackHistoryEntry(
                requester=requester,
                bot=self.hanabi.bot.conf.name,
                track_title=event.track.info.title,
                track_source=event.track.info.uri
            )
            await entry.asave()
            
    async def on_track_end(self, event):
        """Callback for TrackEnd event."""
        # Acquire session lock to prevent dumb
        async with self.lock:
            # Set the last track completion to the current UNIX timestamp.
            self._last_track_completion = time.time()

            # If the track finished, we can tell the player embed
            # to "complete" itself. Otherwise, we should just stop it.
            if event.reason == "finished":
                await self._player_embed.complete()
            else:
                await self._player_embed.stop()

            # Set is_playing to False and the current track to None.
            # If there is another track, these will be update on TrackStart.
            self._is_playing = False
            self._current_track = None
            
            # If the event is such that we can start the next track...
            if event.may_start_next:
                # Check to see that the repeat mode is ONE.
                if self._repeat_mode is RepeatMode.ONE:
                    # If so, we can just call _play() to begin the current
                    # track anew. No need to set volume here since it will
                    # be the same.
                    await self._play()
                else:
                    # Otherwise, advance the queue.
                    track = self.dadvance()
                    if self._repeat_mode is RepeatMode.NONE:
                        if track is not None:
                            # If repeat mode is NONE and the track from dadvance() is
                            # also none, it means we've reached the end of the queue.
                            # Otherwise, update volume, then begin playback.
                            user = await User.objects.aget(id=track.requester)
                            self._volume = user.volume
                            await self._play()
                    elif self._repeat_mode is RepeatMode.ALL:
                        if track is None:
                            # If the repeat mode is ALL and the track is none, then
                            # we want to begin again, so we advance back to track #1.
                            track = self.dadvance_to(1)
                            user = await User.objects.aget(id=track.requester)
                            self._volume = user.volume
                        await self._play()
    
    async def on_player_update(self, event):
        """Callback for PlayerUpdate events."""
        # Acquire lock because...you know.
        async with self.lock:
            # Check that the player embed isn't null.
            if self._player_embed is not None:
                # If it isn't, update the active player embed.
                # Since Lavalink is configured to send these every 2
                # seconds, this takes place roughly that frequent.
                await self._player_embed.update()
            
            # We need to handle user-defined track ends:
            # Chrissy wake up!
            track = self.dget_current() # I
            if track is not None and event.state is not None: # don't
                if track.end_at is not None: # like
                    if track.end_at <= self._state.position: # this!
                        await self.seek(track.info.length)

