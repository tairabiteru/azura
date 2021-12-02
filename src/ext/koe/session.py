from core.conf import conf
from ext.utils import aio_get
from ext.ctx import create_timeout_message
from ext.koe.queue import KoeQueue, PositionError
from ext.koe.objects import Repeat
from ext.koe.exceptions import BadResponse, NoExistingSession, TrackNotFound

import aiohttp
import asyncio


class KoeBaseSession:
    def __init__(self, gid, vid, cid):
        """
        Define session upon which all other sessions are based.

        A session represents a single connection event between the bot and a
        voice channel. There can be only one session per voice channel, and
        there can be only one session per server.
        This class is never directly instantiated, and is instead only used as
        the parent of other sessions defined below.

        ...

        Attributes
        ----------
        session: typing.Union[LocalKoeSession, ChildKoeSession]
            The session to which this message is attached.
        stream: hikari.api.event_manager.EventStream
            The event stream attached to the interaction listener, if any.

        gid: int
            The ID of the guild associated with the session.
        vid: int
            The ID of the voice channel associated with the session.
        cid: int
            The ID of the text channel associated with the session.

        Methods
        -------
        decode_track(track: str)
            Decode a base64 string using the Lavalink endpoint.
            This method only exists as a bandage on an issue with Lavasnek_rs.

        """
        self.gid = gid
        self.vid = vid
        self.cid = cid

    @staticmethod
    async def decode_track(track):
        """
        Decode a base64 string to a track using the Lavalink endpoint.

        This method only exists to fix an issue currently present in Lavasnek_rs
        and will be removed in future versions when the issue is fixed.

        Parameters
        ----------
        track: str
            The base64 track string to decode.

        Returns
        -------
        typing.Dict[typing.Any, typing.Any]

        """
        dest = f"http://{conf.audio.lavalink_addr}:{conf.audio.lavalink_port}/decodetrack?track={track}"
        headers = {
            'Authorization': conf.audio.lavalink_pass
        }
        return await aio_get(dest, headers=headers, fmt="json")


class LocalKoeSession(KoeBaseSession):
    """
    Define LocalKoeSession for sessions local to the parent bot.

    A LocalKoeSession represents a session which has been instantiated and is to
    be handled by the parent bot. It defines a session in which external
    communication is largely unnecessary. The methods defined here largely
    define sessions as a whole, because ChildKoeSession (the child bot
    counterpart) inherits from it, and RemoteKoeSession largely acts as a
    connector to a ChildKoeSession.
    This class is only instantiated on the parent bot.

    ...

    Attributes
    ----------
    bot: core.bot.Master
        The parent bot to which this session belongs.
    now_playing_message: ext.koe.objects.NowPlayingMessage
        The now playing message. Represents the playback message that appears
        whenever the bot plays music.
    queue: ext.koe.queue.KoeQueue
        The queue which holds all songs in a session, past and present.
    _lock: asyncio.Lock
        A lock which controls manipulation of protected variables.
    _enqueueLock: asyncio.Lock
        A lock which prevents enqueueing while enqueueing is already happening.
    _repeat_mode: ext.koe.objects.Repeat
        The current repeat mode of the session.
    _volume: int
        The current volume setting of the session.
    _state: str
        The current state of the session. (This should prolly be an Enum)
    _paused: bool
        Whether or not the session is paused.

    Methods
    -------
    isPaused()
        Accessor method for _paused.
    volumeLevel()
        Accessor method for _volume.
    state()
        Accessor method for _state.
    repeatMode()
        Accessor method for _repeat_mode.
    setState(state: str)
        Mutator method for _state.
    overwriteNode()
        Overwrites the current node queue and now_playing with the current
        queue and track respectively.
    delete()
        Deletes this session from the Koe instance connected to the bot
        associated with this session.
    connect()
        Connects this session to the guild. This also adds the session to the
        Koe instance associated with the owning bot.
    disconnect()
        Disconnects this session from the guild. This also calls delete(),
        removing the session from the Koe instance associated with the owning
        bot.
    play(uid: int, query: str)
        Adds a song to the queue, and starts playback if it's not already
        playing.
    pause(setting: typing.Union[bool, str] = "toggle")
        Mutator method for _paused. The string "toggle" can be passed as well
        to simply switch out of whatever the state was. Also actually sets
        pause on the player itself.
    volume(setting: int)
        Mutator method for _volume. Also actually sets playback volume.
    repeat(setting: ext.koe.objects.Repeat)
        Mutator method for _repeat_mode.
    move_to(position: int)
        Changes the queue to the position specified. This immediately cancels
        the current song playing and switches to the song of the position.
    move_by(positions: int, stop: bool)
        Moves the queue backward or forward by the number of positions
        specified. Forward if positive, backwards if negative.
    enqueueFilePlaylist(files: typing.List[str])
        Enqueues a list of files.

    """
    def __init__(self, bot, gid, vid, cid):
        """
        Construct attributes for LocalKoeSession.

        Parameters
        ----------
        bot: core.bot.Master
            The bot associated with this session.
        gid: int
            The ID of the guild associated with this session.
        vid: int
            The ID of the voice channel associated with this session.
        cid: int
            The ID of the text channel associated with this session.

        """
        self.bot = bot
        self.now_playing_message = None
        self.queue = KoeQueue()

        self._lock = asyncio.Lock()
        self._enqueueLock = asyncio.Lock()

        self._repeat_mode = Repeat.NONE
        self._volume = 100
        self._state = None
        self._paused = False

        super().__init__(gid, vid, cid)

    async def isPaused(self):
        """
        Accessor method for _paused.

        Returns
        -------
        bool

        """
        async with self._lock:
            return self._paused

    async def volumeLevel(self):
        """
        Accessor method for _volume.

        Returns
        -------
        int

        """
        async with self._lock:
            return self._volume

    async def state(self):
        """
        Accessor method for _state.

        Returns
        -------
        str

        """
        async with self._lock:
            return self._state

    async def repeatMode(self):
        """
        Accessor method for _repeat_mode.

        Returns
        -------
        koe.ext.objects.Repeat

        """
        async with self._lock:
            return self._repeat_mode

    async def setState(self, state):
        """
        Mutator method for _state.

        Parameters
        ----------
        state: str
            The current state of the player.

        Returns
        -------
        None

        """
        async with self._lock:
            self._state = state

    async def overwriteNode(self):
        """
        Overwrite the current node queue and track with what's stored in _queue.

        Returns
        -------
        None

        """
        node = await self.bot.lavalink.get_guild_node(self.gid)
        current_tracks = await self.queue.currentTracks()
        node.queue = current_tracks
        node.now_playing = current_tracks[0]
        await self.bot.lavalink.set_guild_node(self.gid, node)

    async def delete(self):
        """
        Delete this session, removing it from the associated bot's koe instance.

        Returns
        -------
        None

        """
        await self.bot.koe.delSession(self)

    async def connect(self):
        """
        Connect this session to voice. This also adds the session to the owning
        bot's koe instance.

        Returns
        -------
        None

        """
        await self.bot.update_voice_state(self.gid, self.vid)
        info = await self.bot.lavalink.wait_for_full_connection_info_insert(self.gid)
        await self.bot.lavalink.create_session(info)
        await self.bot.koe.addSession(self)
        await create_timeout_message(self.bot, self.cid, "Connected.", 5)

    async def disconnect(self):
        """
        Disconnect this session from voice. This also removes the session from
        the owning bot's koe instance.

        Returns
        -------
        None

        """
        await self.bot.lavalink.stop(self.gid)
        await self.delete()
        await self.bot.lavalink.destroy(self.gid)
        await self.bot.update_voice_state(self.gid, None)
        await self.bot.lavalink.wait_for_connection_info_remove(self.gid)
        await self.bot.lavalink.remove_guild_node(self.gid)
        await self.bot.lavalink.remove_guild_from_loops(self.gid)
        await create_timeout_message(self.bot, self.cid, "Disconnected.", 5)
        await self.now_playing_message.close()

    async def play(self, uid, query):
        """
        Play the track specified by the query. The query can be a Youtube link,
        or a search for a particular song.

        Parameters
        ----------
        uid: int
            The ID of the user who requested playback.
        query: str
            The search term or URL to enqueue.

        Returns
        -------
        None

        """
        async with self._enqueueLock:
            track = await self.bot.lavalink.auto_search_tracks(query)
            if len(track.tracks) == 0:
                raise TrackNotFound
            track = track.tracks[0]
            track = self.bot.lavalink.play(self.gid, track).requester(uid).to_track_queue()
            await self.queue.append(track)

            if (await self.state()) is None:
                await self.bot.lavalink.play(self.gid, track.track).requester(uid).start()
            elif (await self.state()) not in ["Playing", "Paused"]:
                await self.queue.move(1)
                await self.bot.lavalink.play(self.gid, track.track).requester(uid).start()
            await self.overwriteNode()

    async def pause(self, setting="toggle"):
        """
        Mutator method for _paused. This also pauses the player itself when
        the setting is true. If the setting is "toggle", then the pause state
        will be switched to the opposite of whatever it was. Returns whatever
        the pause setting is after being set.

        Parameters
        ----------
        setting: typing.Union[bool, str]
            Whether or not the player should be paused or unpaused.

        Returns
        -------
        bool

        """
        if setting == "toggle":
            node = await self.bot.lavalink.get_guild_node(self.gid)
            if node.is_paused:
                setting = False
            else:
                setting = True
        await self.bot.lavalink.set_pause(self.gid, setting)

        async with self._lock:
            self._paused = setting
            self._state = "Paused" if self._paused else "Playing"
        return setting

    async def volume(self, setting):
        """
        Mutator method for _volume. This also changes the actual volume level of
        the player.

        Parameters
        ----------
        setting: int
            The volume to set.

        Returns
        -------
        None

        """
        async with self._lock:
            self._volume = setting
            await self.bot.lavalink.volume(self.gid, setting)

    async def repeat(self, setting):
        """
        Mutator method for _repeat_mode.

        Parameters
        ----------
        setting: ext.koe.objects.Repeat
            The repeat mode to set.

        Returns
        -------
        None

        """
        async with self._lock:
            self._repeat_mode = setting

    async def move_to(self, position):
        """
        Move to a particular position in the queue.

        Parameters
        ----------
        position: int
            The position to jump to.

        Returns
        -------
        None

        """
        await self.queue.set_pos(position)
        await self.bot.lavalink.stop(self.gid)
        track = await self.queue.currentTracks()
        track = track[0]
        await self.bot.lavalink.play(self.gid, track.track).requester(track.requester).start()
        await self.overwriteNode()

    async def move_by(self, positions, stop=False):
        """
        Move the queue by the number of positions specified. This also
        implements skip behavior by passing in 1 as the positions. If stop is
        set, the playback will be stopped if the queue is at the end.

        Parameters
        ----------
        positions: int
            The number of positions to move forward or backward. (if negative)
        stop: bool
            Whether or not playback should be stopped if the queue is at the end.

        Returns
        -------
        None

        """
        try:
            await self.queue.move(positions)
        except PositionError:
            if positions == 1 and stop is True:
                await self.bot.lavalink.stop(self.gid)
            raise

        await self.bot.lavalink.stop(self.gid)
        track = await self.queue.currentTracks()
        track = track[0]
        await self.bot.lavalink.play(self.gid, track.track).requester(track.requester).start()
        await self.overwriteNode()

    async def enqueueFilePlaylist(self, files):
        """
        Enqueue a series of files.

        Parameters
        ----------
        files: typing.List[str]
            A list of str containing absolute file paths.

        Returns
        -------
        None

        """
        async with self._enqueueLock:
            for file in files:
                track = await self.bot.lavalink.get_tracks(file)
                if len(track.tracks) == 0:
                    raise TrackNotFound
                track = track.tracks[0]
                track = self.bot.lavalink.play(self.gid, track).to_track_queue()
                await self.bot.lavalink.play(self.gid, track.track).queue()
                await self.queue.append(track)
                if (await self.bot.lavalink.get_guild_node(self.gid)).now_playing is None:
                    await self.queue.move(1)
                await self.overwriteNode()


class ChildKoeSession(LocalKoeSession):
    """
    Define ChildKoeSession for sessions local to child bots.

    A ChildKoeSession represents a session which is present and being handled by
    a child bot rather than the parent bot. ChildKoeSession operates in much the
    same way as LocalKoeSession, but with some differences in methods to ensure
    sessions remain consistent between parent and child.
    This class is only instantiated by child bots.

    ...

    Methods
    -------
    serialize()
        Creates a dict of the relevant attributes for POSTing.
    post()
        Sends a POST request to the specified API path at the parent bot's
        endpoint. This method communicates ONLY with the parent bot.
    delete()
        Removes the bot from the PARENT bot's koe instance, then also deletes
        itself from the child bot's koe instance.
    disconnect()
        Does exactly the same thing as LocalKoeSession.disconnect(), but it also
        calls ChildKoeSession.delete(), informing the parent of the removal for
        session consistency.

    """
    def __init__(self, bot, gid, vid, cid):
        super().__init__(bot, gid, vid, cid)

    def serialize(self):
        return {'gid': self.gid, 'vid': self.vid, 'cid': self.cid}

    async def post(self, api_path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://{conf.dash.host}:{conf.dash.port}{api_path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                resp = await response.json()
        if 'response' not in resp:
            raise BadResponse(resp)

    async def delete(self):
        data = self.serialize()
        await self.post("/api/session/delete", data)
        await super().delete()

    async def disconnect(self):
        await super().disconnect()
        await self.delete()


class RemoteKoeSession(KoeBaseSession):
    """
    Define RemoteKoeSession for sessions remote to the parent bot.

    A RemoteKoeSession represents a session which is to be handled by a bot
    other than the parent bot. RemoteKoeSession operates using web endpoints to
    instruct child bots on what to do. They act almost like a pipeline between
    the parent's koe instance, and a child's koe instance. Each RemoteKoeSession,
    when connected, spawns a counterpart ChildKoeSession on the child bot which
    handles the request.
    This class is only instantiated on the parent bot.

    ...

    Attributes
    ----------
    bot: core.bot.Master
        The parent bot to which this session belongs.
    endpoint: str
        The endpoint of the webserver of the child bot assigned to playback.

    Methods
    -------
    serialize()
        Creates a dict of the relevant attributes for POSTing.
    post()
        Sends a POST request to the specified API path at the endpoint
        associated with the session.

    """
    def __init__(self, bot, endpoint, gid, vid, cid):
        self.bot = bot
        self.endpoint = endpoint
        super().__init__(gid, vid, cid)

    def serialize(self):
        return {'gid': self.gid, 'vid': self.vid, 'cid': self.cid}

    async def post(self, api_path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}{api_path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                resp = await response.json()
        if 'response' not in resp:
            raise BadResponse(resp)
        elif resp['response'] == "NoExistingSession":
            raise NoExistingSession(data['vid'])
        elif resp['response'] == "PositionError":
            raise PositionError(resp['message'])
        return resp

    async def delete(self):
        await self.post("/api/session/delete", self.serialize())

    async def connect(self):
        await self.post("/api/voice/connect", self.serialize())
        await self.bot.koe.addSession(self)

    async def disconnect(self):
        await self.post("/api/voice/disconnect", self.serialize())
        await self.bot.koe.delSession(self)

    async def stop(self):
        await self.post("/api/voice/stop", self.serialize())

    async def play(self, uid, query):
        data = self.serialize()
        data['uid'] = uid
        data['query'] = query
        await self.post("/api/voice/play", data)

    async def pause(self, setting="toggle"):
        data = self.serialize()
        data['setting'] = setting
        await self.post("/api/voice/pause", data)

    async def volume(self, setting):
        data = self.serialize()
        data['setting'] = setting
        await self.post("/api/voice/volume", data)

    async def move_to(self, position):
        data = self.serialize()
        data['position'] = position
        await self.post("/api/voice/move/to", data)

    async def move_by(self, positions, stop=False):
        data = self.serialize()
        data['positions'] = positions
        data['stop'] = stop
        await self.post("/api/voice/move/by", data)
