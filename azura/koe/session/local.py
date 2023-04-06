from core.conf import conf
from core.subroutines import execute_in_background
from ext.ctx import create_timeout_message
from ext.utils import utcnow

from koe.session.base import Session
from koe.objects import PlaybackControls, NowPlayingEmbed
from koe.queue import Queue
from koe.enums import EnqueueMode, RepeatMode, SessionState
from koe.errors import InvalidPosition

import orm.models as models

import asyncio
import datetime
import hikari
import lavasnek_rs
import random


def track_event(func):
    async def wrapper(self, event):
        async with self.session_lock:
            value = await func(self, event)
            self._last_event = event
            return value
    return wrapper


class LocalSession(Session):
    """
    An implementation of a LocalSession, I.E, one which is local
    to the bot containing it. For a description of a session, see the
    Session class definition.

    This class contains a myriad of methods, but only some should be called
    outside of the class itself. TYPICALLY, methods prefixed with _ should NOT
    be called outside of the class itself, and can be considered private. The
    same more or less can be said for attributes like that.

    Many of the "private" methods and attributes are private because they require
    that a lock be acquired before reading/writing/altering. It is *extremely* unwise
    to do so willy nilly, as this easily leads to very difficult to troubleshoot
    race conditions. Nonetheless, the unsafe methods are provided because at times,
    (especially in the class itself) you need to call a function while a lock has been
    acquired, and you can't exactly do that if the function also acquires the lock.

    Hence, all of this. So, past developer, when you read back upon this and ponder
    why this is so stupid, know that you already pondered this question when
    writing it.
    """
    def __init__(self, bot, guild_id, voice_id, channel_id):
        super().__init__(bot, guild_id, voice_id, channel_id)

        self.session_lock = asyncio.Lock()
        self.enqueue_lock = asyncio.Lock()

        self._queue = Queue()
        self._state = SessionState.NEW
        self._paused = False
        self._repeat_mode = RepeatMode.NONE
        self._volume = 100
        self._listen_to_events = True

        self._now_playing_message = None
        self._now_playing_embed = None
        self._playback_controls = None
        self._last_event = None
        self._last_track_finish = None
        self._idle_process = None
    
    # --- BEGIN PRIVATE METHOD DEFINITIONS ---
    async def _advance(self):
        """
        Advancement needs to happen all within one go, and with both the queue
        and session locks acquired.  This is the reason this function is so stupid.
        """
        start = True
        async with self._queue._lock:
            if self._repeat_mode is RepeatMode.NONE or self._repeat_mode is RepeatMode.ALL:
                try:
                    self._queue._advance_by(1)
                except InvalidPosition as e:
                    self._state = SessionState.ENDED
                    if not self._queue._is_at_end():
                        raise e
                    
                    if self._repeat_mode is RepeatMode.ALL:
                        self._queue._set_position_to(0)
                    else:
                        start = False
                        self._last_track_finish = utcnow()
                        self._idle_process = execute_in_background(self._do_idle_process())
                        await self._send_message("The end of the queue has been reached.")
                        return False
            
            if start is True:
                track = self._queue._get_current_track()
                builder = self.lavalink.play(self.guild_id, track.track)
                builder.requester(track.requester)
                await builder.start()

                # Need to update the node without locking the queue
                node = await self.lavalink.get_guild_node(self.guild_id)
                node.queue = self._queue._get_current_tracks_list()
                node.now_playing = node.queue[0]
                await self.lavalink.set_guild_node(self.guild_id, node)
            return True
    
    # DANGEROUS! - This should only be called inside of the Koe manager!
    async def _connect(self):
        """
        This method isn't *technically* private, as it gets called outside of
        this class, however it might as well be. It is ONLY to be called inside
        of the Koe manager.
        """
        t = await self.bot.update_voice_state(self.guild_id, self.voice_id)
        print(t)
        info = await self.lavalink.wait_for_full_connection_info_insert(self.guild_id)
        await self.lavalink.create_session(info)
        await self._send_message(f"{self.bot.name.capitalize()}, responding to connection request.", timeout=15)

    # DANGEROUS! - This should only be called inside of the Koe manager!
    async def _disconnect(self):
        """
        Pretty much the same as above, except this method is even more touchy.
        """
        if self._idle_process is not None:
            if not self._idle_process.cancelled():
                self._idle_process.cancel()

        if self._now_playing_message is not None:
            self._now_playing_embed.state = (SessionState.DISCONNECTED).value
            self._now_playing_embed.update()

            try:
                self._playback_controls.stop()
                self._playback_controls = None
            except KeyError:
                pass

            await self.bot.rest.edit_message(self.channel_id, self._now_playing_message, embed=self._now_playing_embed, components=[])

        await self.lavalink.stop(self.guild_id)
        await self.lavalink.destroy(self.guild_id)
        await self.bot.update_voice_state(self.guild_id, None)
        try:
            await self.lavalink.wait_for_connection_info_remove(self.guild_id)
            await self.lavalink.remove_guild_node(self.guild_id)
            await self.lavalink.remove_guild_from_loops(self.guild_id)
            await self._send_message(f"{self.bot.name.capitalize()}, disconnected.", timeout=15)
        except TimeoutError:
            pass
    
    async def _display_playback(self):
        """
        This function is the "unsafe" version of display_playback. I.E,
        it fires without acquiring the necessary lock.
        """
        if self._playback_controls:
            self._playback_controls.stop()

        self._playback_controls = PlaybackControls(self)
        self._now_playing_message = await self._send_message(self._now_playing_embed, components=self._playback_controls.build())
        await self._playback_controls.start(self._now_playing_message)
    
    async def _enqueue(self, requester, track, position=-1):
        async with self.session_lock:
            builder = self.lavalink.play(self.guild_id, track)
            track = builder.requester(requester.id).to_track_queue()
            if position == -1:
                await self._queue.append(track)
            else:
                await self._queue.insert(track, position-1)

            if self._state is not SessionState.PLAYING:
                if self._state is not SessionState.NEW:
                    await self._queue.advance_by(1)
                await self._update_node_unsafe()
                await builder.start()
                self._state = SessionState.PLAYING
    
    async def _fire_player_update(self):
        if self._now_playing_embed is not None and self._playback_controls is not None and self._now_playing_message is not None:
            self._now_playing_embed.state = self._state.value
            self._now_playing_embed.volume = self._volume
            self._now_playing_embed.repeat = self._repeat_mode.value
            self._now_playing_embed.queue = await self._queue.get_contents()
            self._now_playing_embed.update()

            await self._playback_controls._update()
            self._now_playing_message = await self.bot.rest.edit_message(
                self.channel_id,
                message=self._now_playing_message,
                content=self._now_playing_embed,
                components=self._playback_controls.build()
            )
    
    async def _get_repeat_mode(self):
        async with self.session_lock:
            return self._repeat_mode
    
    async def _get_state(self):
        async with self.session_lock:
            return self._state
    
    async def _get_volume(self):
        async with self.session_lock:
            return self._volume

    async def _send_message(self, message, components=[], timeout=None):
        if timeout is not None:
            await create_timeout_message(self.bot, self.channel_id, message, timeout)
        else:
            return await self.bot.rest.create_message(self.channel_id, message, components=components)
    
    async def _set_pause(self, setting="toggle"):
        async with self.session_lock:
            if setting == "toggle":
                setting = not (await self.lavalink.get_guild_node(self.guild_id)).is_paused
            await self.lavalink.set_pause(self.guild_id, setting)
            self._paused = setting
            if self._paused is True:
                self._state = SessionState.PAUSED
            else:
                self._state = SessionState.PLAYING

            if self._state is not SessionState.PLAYING:
                await self._fire_player_update()
            return self._paused
    
    async def _set_volume(self, setting):
        async with self.session_lock:
            await self.lavalink.volume(self.guild_id, setting)
            self._volume = setting

            if self._state is not SessionState.PLAYING:
                await self._fire_player_update()
    
    async def _signal_termination_to_parent(self):
        if self.bot.type.value == "PARENT":
            return

        return await self._post(
            f"http://{conf.parent.host}:{conf.parent.port}/api/destroy_session",
            data=self.serialized
        )

    async def _skip(self, to=None, by=None):
        if to is None and by is None:
            raise ValueError("One of the `to` and `by` parameters must be set.")

        async with self.session_lock:
            if to is not None:
                await self._queue.set_position_to(to)
            if by is not None:
                if self._state in [SessionState.PLAYING, SessionState.PAUSED]:
                    await self._queue.advance_by(by)

            await self.lavalink.stop(self.guild_id)
            track = (await self._queue.get_current_tracks_list())[0]
            builder = self.lavalink.play(self.guild_id, track.track)

            if track.requester is not None:
                builder.requester(track.requester)

            await builder.start()
            await self._update_node_unsafe()
            self._state = SessionState.PLAYING
            return track

    async def _update_node_unsafe(self):
        node = await self.lavalink.get_guild_node(self.guild_id)
        node.queue = await self._queue.get_current_tracks_list()
        node.now_playing = node.queue[0]
        await self.lavalink.set_guild_node(self.guild_id, node)
    
    async def _do_idle_process(self):
        try:
            wait_for = random.randint(600, 900)
            die = random.randint(100, 300)

            while self.bot.is_alive:
                if self._last_track_finish is not None:
                    delta = utcnow() - self._last_track_finish
                    if delta.total_seconds() > wait_for:
                        randint = random.randint(1, die)
                        if randint == 1:
                            die -= random.randint(1, 10)
                            async with self.session_lock:
                                info = await self.bot.lavalink.get_tracks("/home/taira/azura/azura/assets/bttb_intro.mp3")
                                await self.bot.lavalink.play(self.guild_id, info.tracks[0]).queue()
                            
                            if die < 90:
                                randint = random.randint(1, 10)
                                if randint == 10:
                                    await self.bot.koe.destroy_session(self.voice_id)
                await asyncio.sleep(1)
        except Exception as e:
            print(e)
    
    # --- BEGIN ENDPOINT DEFINITIONS ---
    async def display_playback(self):
        async with self.session_lock:
            return await self._display_playback()
    
    async def display_queue(self, amount=5):
        embed = await self._queue.get_embed(amount=amount)
        await self._send_message(embed)
    
    async def enqueue(self, requester: hikari.User, playlist: str, shuffle: bool=False, mode:  str="FIFO", user: hikari.User=None):
        user = requester if user is None else user
        user = await models.User.get_or_create(user)

        if user.hikari_user == requester:
            username = "You do"
        else:
            username = f"{user.hikari_user.username} does"

        playlist_obj = await models.Playlist.get_or_none(owner=user.hikari_user, name=playlist)
        if not playlist_obj:
            return await self._send_message(f"{username} not have a playlist named `{playlist}`.")
        
        playlist = playlist_obj
        if user.hikari_user != requester and not playlist.is_public:
            return await self._send_message(f"The playlist `{playlist.name}` is owned by {playlist.owner.username}, and is not public, so you cannot enqueue it.")
        
        entries = await playlist.items.all()
        if shuffle is True:
            random.shuffle(entries)

        for i, entry in enumerate(entries):
            result = await self.lavalink.auto_search_tracks(entry.source)
            if len(result.tracks) == 0:
                await self._send_message(f"Enqueueing `{entry.title}` failed. No tracks found at that source.")
                continue
            track = result.tracks[0]
            builder = self.lavalink.play(self.guild_id, track)
            if entry.start != 0:
                builder = builder.start_time_secs(entry.start)
            if entry.end != -1:
                builder = builder.finish_time_secs(entry.end)
            track = builder.requester(requester.id).to_track_queue()

            async with self.session_lock:
                async with self._queue._lock:
                    if mode == "FIFO":
                        self._queue._queue.append(track)
                    elif mode == "LIFO":
                        self._queue._queue.insert(self._queue._pos+1, track)
                    elif mode == "RANDOM":
                        pos = random.randint(self._queue._pos+1, len(self._queue._queue)-1)
                        self._queue._queue.insert(pos, track)
                    elif mode == "INTERLACE":
                        factor = len(self._queue._get_unique_requesters(all_except=[requester.id])) + 1
                        pos = ((i * factor) + factor) + self._queue._pos
                        self._queue._queue.insert(pos, track)

                if self._state is not SessionState.PLAYING:
                    if self._state is not SessionState.NEW:
                        await self._queue.advance_by(1)
                    await self._update_node_unsafe()
                    await builder.start()
                    self._state = SessionState.PLAYING
    
        await self._send_message("Enqueueing process finished.")
    
    async def pause(self, internal=False):
        setting = await self._set_pause()
        setting = "" if setting else "un"

        if not internal:
            await self._send_message(f"The player has been {setting}paused.")
    
    async def play(self, requester, query, position=-1):
        result = await self.lavalink.auto_search_tracks(query)
        if len(result.tracks) == 0:
            return await self._send_message(f"The query for `{query}` returned no results.")
        track = result.tracks[0]

        state = await self._get_state()
        verb = "Enqueueing" if state is SessionState.PLAYING else "Playing"
        if state != SessionState.PLAYING:
            user = await models.User.get_or_create(requester)
            await self.set_volume(requester, setting=user.last_volume, internal=True)
        await self._send_message(f"{verb} `{track.info.title}` for {requester.username}.", timeout=15)
        await self._enqueue(requester, track, position=position)
    
    async def set_repeat_mode(self, setting: RepeatMode):
        async with self.session_lock:
            self._repeat_mode = setting
            if self._state is not SessionState.PLAYING:
                await self._fire_player_update()

    async def set_volume(self, user, setting=None, increment=None, internal=False):
        if setting is None and increment is None:
            raise ValueError("One of increment or setting must be set.")

        if setting is not None and increment is not None:
            raise ValueError("Only one of increment or setting can be set.")

        if increment is not None:
            current = await self._get_volume()
            setting = current + increment

        await self._set_volume(setting)
        user = await models.User.get_or_create(user)
        user.last_volume = setting
        await user.save()

        if not internal:
            await self._send_message(f"Volume set to {setting}%.", timeout=10)
        await self._fire_player_update()
    
    async def skip(self, requester, to=None, by=None):
        try:
            track = await self._skip(to=to, by=by)
        except InvalidPosition as e:
            if by is not None:
                verb = "forward" if by > 0 else "backward"
                return await self._send_message(f"You cannot skip {verb} anymore. You have reached the end of the queue.")
            return await self._send_message(str(e))

        await self._send_message(f"{requester.username} skipped to: `{track.track.info.title}`.")

    # --- BEGIN EVENT HANDLER DEFINITIONS ---
    async def handle_track_start(self, event: lavasnek_rs.TrackStart):
        track = await self.lavalink.decode_track(event.track)
        if track.uri != "/home/taira/azura/azura/assets/bttb_intro.mp3":
            async with self.session_lock:
                if self._idle_process is not None:
                    if not self._idle_process.cancelled():
                        self._idle_process.cancel()
                # Ensure paused state remains through track skips
                if self._state == SessionState.PAUSED:
                    await self.lavalink.set_pause(self.guild_id, True)
                
                # Add history record
                await models.TrackHistoryRecord.from_track_start_event(event, self)

                # Set up the playback embed and controls
                assert self._playback_controls == None
                
                self._now_playing_embed = await NowPlayingEmbed.from_session(self, self._volume, self._state, position=0)
                self._playback_controls = PlaybackControls(self)
                self._now_playing_message = await self._send_message(
                    self._now_playing_embed,
                    components=self._playback_controls.build()
                )
                await self._playback_controls.start(self._now_playing_message)
                self._last_event = event

    async def handle_track_finish(self, event: lavasnek_rs.TrackFinish):
        track = await self.lavalink.decode_track(event.track)
        if track.uri != "/home/taira/azura/azura/assets/bttb_intro.mp3":
            async with self.session_lock:
                if event.reason == "FINISHED":
                    if (await self._queue.is_at_end()):
                        await self._playback_controls._update()
                        components = self._playback_controls.build()
                    else:
                        self._playback_controls.stop()
                        components = []
                    await self._advance()
                
                if event.reason == "STOPPED":
                    self._playback_controls.stop()
                    components = []
                
                self._now_playing_embed.state = (SessionState.ENDED).value
                self._now_playing_embed.position = -1
                self._now_playing_embed.update()
                self._now_playing_message = await self.bot.rest.edit_message(
                    self.channel_id,
                    message=self._now_playing_message,
                    content=self._now_playing_embed,
                    components=components
                )
                self._last_event = event
    
    async def handle_player_update(self, event: lavasnek_rs.PlayerUpdate):
        current = await self._queue.get_current_track()
        if current.end_time is not None:
            if event.state_position >= (await self._queue.get_current_track()).end_time:
                await self._skip(by=1)

        async with self.session_lock:
            if self._now_playing_message is not None:
                if self._last_event is lavasnek_rs.lavasnek_rs.TrackFinish:
                        return
                        
                self._now_playing_embed.position = event.state_position
                self._now_playing_embed.state = self._state.value
                self._now_playing_embed.volume = self._volume
                self._now_playing_embed.repeat = self._repeat_mode.value
                self._now_playing_embed.queue = await self._queue.get_contents()
                self._now_playing_embed.update()


                await self._playback_controls._update()

                elapsed = utcnow() - self._now_playing_message.timestamp
                if elapsed >= datetime.timedelta(seconds=conf.message_resend_interval):
                    await self._display_playback()
                else:
                    self._now_playing_message = await self.bot.rest.edit_message(
                        self.channel_id,
                        message=self._now_playing_message,
                        content=self._now_playing_embed,
                        components=self._playback_controls.build()
                    )
            self._last_event = event