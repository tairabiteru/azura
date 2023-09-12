from .events import StatsEvent, PlayerUpdateEvent, TrackStartEvent, TrackEndEvent, TrackExceptionEvent
from .objects import HttpMethod, Player, Track
from .utils import cc_to_sc_dict
from .sessions import BaseSession, LocalSession, RemoteSession
from .interop import Operation
from .errors import NoSessionExists, SessionAlreadyExists, NotAvailable, InvalidName
from .embeds import generate_volume_bar

import aiohttp
import asyncio
import collections
import hikari
import orjson as json
import time
import traceback
import typing
import websockets


__author__ = "Taira"
__version__ = "1.0.0"


def require_voice(auto_connect=False):
    """
    Decorator for Hikari Lightbulb commands.

    Commands with this decorator force the requirement that the author is within
    a voice channel accessible to Azura. The single kwarg 'auto_connect' tells
    whether or not Azura will automatically attempt to create a session.

    tl;dr, this decorator prefixes commands that require voice. If auto_connect
    is True, Azura will connect herself if she isn't already. If it's False,
    she'll fail to execute the command if she's not already connected.
    """
    def inner(command):
        async def wrapper(ctx):
            user_state = ctx.bot.cache.get_voice_state(ctx.guild_id, ctx.author.id)
            if user_state is None:
                return await ctx.respond("You must be connected to a voice channel to use this command.")
            
            try:
                session = await ctx.bot.hanabi.get_session(user_state.channel_id)
                return await command(ctx, session)
            except NoSessionExists:
                if auto_connect is False:
                    return await ctx.respond("There must be an existing voice session with either me or one of my children to use this command.")
                
                if hasattr(ctx.options, "bot"):
                    if ctx.options.bot is not None:
                        if ctx.author.id != ctx.bot.conf.owner_id:
                            return await ctx.respond("Only my owner can specify which bot connects.")
                        session = await ctx.bot.hanabi.create_session_with(ctx.options.bot, ctx.guild_id, user_state.channel_id, ctx.channel_id)
                        return await command(ctx, session)
                
                session = await ctx.bot.hanabi.create_session(ctx.guild_id, user_state.channel_id, ctx.channel_id)
                return await command(ctx, session)
        return wrapper
    return inner


class Hanabi:
    def __init__(self, bot, host="localhost", port=2333, password="", ssl=False, user_id=None, loop=None):
        """
        Hanabi management object. The core of the session management system.

        To give a *very* brief overview, Hanabi has two separate but related jobs:

        1) Hanabi is responsible for interfacing with Lavalink.
        2) Hanabi is responsible for the management of voice sessions.

        The way Hanabi interfaces with Lavalink isn't groundbreaking, and
        it's done almost the same way any other wrapper does it. The management
        of voice sessions in Hanabi is unique though, and if you'd like to know
        more about it, read the README or read the docstrings for create_session().

        LocalSessions can be minted either by the parent bot, or by a child, via the
        parent. RemoteSessions can be only minted by the parent, and are ultimately
        connected (over a websocket connection) to a LocalSession on the child's
        instance of Hanabi.

        To visualize how this fits together, here's an example layout of how Hanabi
        creates local and remote sessions:

                    Parent
                    /    \
        LocalSession     RemoteSession
                                     \
                                      Child
                                          \
                                          LocalSession
        
        In the example, the parent has a LocalSession, an instance in which the
        parent bot is connected to a voice channel. But the parent also has a 
        RemoteSession, an instance where the parent has commanded a child to
        connect to a voice channel.

        As an example, consider how the /play command would operate. During
        execution of the command, Hanabi's get_session() method is called which
        returns either a LocalSession or a RemoteSession depending on how the
        session itself was formed. In the example of a LocalSession, the play_cmd()
        method of the session is directly called, resulting in direct action on
        the part of the parent.
        If the RemoteSession is returned however, the play_cmd() method of the
        RemoteSession is called, which results in a websocket message being sent
        downstream to the child. The child receives that message containing the
        instruction to play, and the child invokes the same play_cmd() method of
        LocalSession, but on *their* side, causing playback to begin on the child.
        """
        self.host = host
        self.port = port
        self.password = password
        self.ssl = ssl
        self.user_id = user_id
        self.bot = bot
        self.loop = loop if loop is not None else asyncio.get_event_loop()

        self._session_id = None
        self._ws_connected = False
        self._sessions = {}
        self._stats_deque = collections.deque(maxlen=100)
        self.lock = asyncio.Lock()
    
    @property
    def session_id(self):
        """Getter for session id."""
        if self._session_id is None:
            raise ValueError("No session ID found.")
        return self._session_id
    
    @property
    def rest_endpoint(self):
        """Returns rest endpoint of lavalink."""
        protocol = "https" if self.ssl is True else "http"
        return f"{protocol}://{self.host}:{self.port}"
    
    @property
    def rest_headers(self):
        """Returns rest headers for lavalink."""
        return {
            'Authorization': self.password
        }
    
    @property
    def ws_endpoint(self):
        """Returns the websocket endpoint for lavalink."""
        protocol = "wss" if self.ssl is True else "ws"
        return f"{protocol}://{self.host}:{self.port}"
    
    @property
    def ws_headers(self):
        """Returns the websocket headers for lavalink."""
        return {
            'Authorization': self.password,
            'User-Id': self.user_id,
            'Client-Name': f"Hanabi on {self.bot.conf.name}/{__version__}"
        }

    @property
    def latest_stats(self):
        """Shortcut to return the latest stats from lavalink."""
        return self._stats_deque[-1]
    
    async def stop(self):
        """
        Stops Hanabi, destroying all sessions in the process.

        This is normally called when the bot shuts down or reboots.
        """
        async with self.lock:
            vids = list([vid for vid in self._sessions.keys()])
            for vid in vids:
                session = self.dget_session(vid)
                await session.disconnect()
    
    def dget_session(self, voice_id: int):
        """Dangerous version of get_session()."""
        session = self._sessions.get(voice_id, None)
        if session is None:
            raise NoSessionExists(f"No session exists for VID {voice_id}.")
        return session

    async def get_session(self, voice_id: int):
        """
        Returns a session given the voice ID.

        "Why does this use the voice ID instead of the guild ID?"
        Because it's possible to have more than one session in a single guild.
        Sessions can either be Local or Remote, and while it's only possible
        to have one Local session per guild on the parent, it IS possible to have
        a LocalSession and a RemoteSession in the same guild. This is the case when
        the parent is connected in one channel, while the child is connected in
        another in the same guild.
        """
        async with self.lock:
            return self.dget_session(voice_id)
    
    def dget_local_session(self, guild_id: int):
        """Dangerous version of get_local_session()"""
        for session in self._sessions.values():
            if isinstance(session, LocalSession) and session.guild_id == guild_id:
                return session
        return None

    async def get_local_session(self, guild_id: int):
        """
        Return the LocalSession given its guild ID.

        As mentioned above, it's possible to have more than one session
        with the same guild ID, but it's not possible for LocalSessions.
        Because of this, we can use the guild ID to take a shortcut if
        the session we're looking for is a local one.
        """
        async with self.lock:
            return self.dget_local_session(guild_id)

    async def dcreate_session(self, guild_id: int, voice_id: int, channel_id: int):
        """Dangerous version of create_session()"""
        session = self._sessions.get(voice_id, None)
        if session is not None:
            raise SessionAlreadyExists(f"Session under VID {voice_id} already exists.")
        
        if self.bot.available_in(guild_id):
            await self.bot.update_voice_state(guild_id, voice_id)
            self._sessions[voice_id] = LocalSession(self, guild_id, voice_id, channel_id)
        elif self.bot.__class__.__name__ == "ParentBot":
            for child_name, connection in self.bot.child_connections.items():
                await connection.send(json.dumps({'op': 'connect', 'guild_id': guild_id, 'voice_id': voice_id, 'channel_id': channel_id}))
                resp = await connection.recv()
                data = json.loads(resp.decode("utf-8"))
                if data['status'] == "SUCCESS":
                    self._sessions[voice_id] = RemoteSession(self, guild_id, voice_id, channel_id, child_name)
                    return self._sessions[voice_id]
            else:
                raise ValueError("No children or parents available.")
        else:
            raise ValueError(f"{self.bot.conf.name} is not available.")
        return self._sessions[voice_id]

    async def create_session(self, guild_id: int, voice_id: int, channel_id: int):
        """
        Create a session given the guild ID, voice channel ID, and text channel ID.

        When this method is called, Hanabi will attempt to create a new voice session.
        In the event one already exists, this will fail, thowing SessionAlreadyExists.
        Otherwise, Hanabi will attempt to mint a LocalSession by checking to see if the
        parent bot is available in the specified guild. If it is, a LocalSession is
        created and returned. If not however, Hanabi will attempt to negotiate with
        any and all children of the parent to create a RemoteSession. The first child
        to respond affirmatively will cause the minting of a RemoteSession
        connected to a LocalSession on the child bot. If no children are available,
        the operation fails with an error.
        """
        async with self.lock:
            return await self.dcreate_session(guild_id, voice_id, channel_id)
    
    async def dcreate_session_with(self, bot: str, guild_id: int, voice_id: int, channel_id: int):
        """Dangerous version of create_session_with()"""
        session = self._sessions.get(voice_id, None)
        if session is not None:
            raise SessionAlreadyExists(f"Session under VID {voice_id} already exists.")
        
        if bot.lower() == self.bot.conf.name.lower():
            if self.bot.available_in(guild_id):
                await self.bot.update_voice_state(guild_id, voice_id)
                self._sessions[voice_id] = LocalSession(self, guild_id, voice_id, channel_id)
            else:
                raise NotAvailable("I'm not available to connect at the moment.")
        else:
            for name, connection in self.bot.child_connections.items():
                if name.lower() == bot.lower():
                    await connection.send(json.dumps({'op': 'connect', 'guild_id': guild_id, 'voice_id': voice_id, 'channel_id': channel_id}))
                    # This technically has a small chance to mess up with RuntimeError.
                    # We have to handle this, but later.
                    resp = await connection.recv()
                    data = json.loads(resp.decode('utf-8'))
                    if data['status'] == "SUCCESS":
                        self._sessions[voice_id] = RemoteSession(self, guild_id, voice_id, channel_id, name)
                        break
                    else:
                        raise NotAvailable(f"{name} is not available to connect at the moment.")
            else:
                raise InvalidName(f"The name `{bot}` could not be resolved into the name of any valid bot.")
        
        return self._sessions[voice_id]

    async def create_session_with(self, bot: str, guild_id: int, voice_id: int, channel_id: int):
        """
        Create a session given the bot name, guild ID, voice ID and text channel ID.

        This operates largely the same as create_session(), except it allows you to
        select which bot is to connect. This is mostly useful for testing.
        In the event that the target bot is not available, this fails with
        an error, similar to how create_session() fails with an error if no
        bots are available.
        """
        async with self.lock:
            return await self.dcreate_session_with(bot, guild_id, voice_id, channel_id)
    
    async def delete_session(self, session_or_vid: typing.Union[int, BaseSession]):
        """
        Delete a session given either the session object itself, or the voice ID.
        
        Unlike destory_session() below, this does not cause the session in
        question to disconnect, or perform any functions which usually happen
        when a session is outright destroyed. There's really only one application
        of this, and that is when a child destroys a session on their own.
        In this case, the child session is connected to a RemoteSession on the
        parent, and the parent needs to be informed of this destruction so the
        parent can do the same. However we don't want it doing anything else,
        because that extra stuff would ultimately just go back to the child,
        who - having just destroyed the session -  will ask what the hell parent
        is talking about.
        """
        async with self.lock:
            voice_id = session_or_vid.voice_id if isinstance(session_or_vid, BaseSession) else session_or_vid
            session = self._sessions.pop(voice_id, None)
            return session
    
    async def ddestroy_session(self, session_or_vid: typing.Union[int, BaseSession]):

        voice_id = session_or_vid.voice_id if isinstance(session_or_vid, BaseSession) else session_or_vid
        session = self._sessions.pop(voice_id, None)
        if session is None:
            raise NoSessionExists(f"No session exists for VID {voice_id}.")
        await session.disconnect()
        if self.bot.__class__.__name__ != "ParentBot":
            await self.bot.send_to_parent(json.dumps({'op': 'delete', 'voice_id': voice_id}))
        await self.request(
            HttpMethod.DELETE,
            f"/v4/sessions/{self.session_id}/players/{session.guild_id}"
        )
        return session

    async def destroy_session(self, session_or_vid: typing.Union[int, BaseSession]):
        async with self.lock:
            return await self.ddestroy_session(session_or_vid)
    
    async def handle_voice_state_update(self, user_id: int, guild_id: int, session_id: str, voice_id: int):
        if user_id != self.user_id:
            return
        
        # Disconnect
        if voice_id is None:
            session = await self.get_local_session(guild_id)
            if session is not None:
                await self.destroy_session(session)
        # VC change or connect
        else:
            session = self._sessions.get(voice_id, None)
            # connect
            if session is None:
                return
                # session = LocalSession(self, guild_id, voice_id, 3893297832)
                # session.dsid = session_id
                # self._sessions[voice_id] = session
            # change
            else:
                self._sessions.pop(voice_id)
                session.guild_id = guild_id
                session.dsid = session_id
                session.voice_id = voice_id
                self._sessions[voice_id] = session

    
    async def handle_voice_server_update(self, guild_id: int, endpoint: str, token: str, voice_id: typing.Optional[int]=None):
        session = await self.get_local_session(guild_id)
        if session is None:
            return

        if voice_id is not None:
            self._sessions.pop(session.voice_id)
            session.voice_id = voice_id
            self._sessions[session.voice_id] = session
        
        if session.voice_id is None:
            await self.destroy_session(session)
            return

        player = await self.update_player(
            guild_id=session.guild_id,
            data={
                'voice': {
                    'token': token,
                    'sessionId': session.dsid,
                    'endpoint': endpoint.replace("wss://", "")
                }
            }
        )

        session._state = player.state
        self._sessions[session.voice_id] = session
    
    def start(self):
        self.loop.create_task(self._ll_ws_loop())
        self.loop.create_task(self._dead_connection_reaper())
        self.loop.create_task(self._child_heartbeat())
    
    async def _child_heartbeat(self):
        if self.bot.__class__.__name__ == "ParentBot":
            while True:
                for child, status in self.bot.children.items():
                    try:
                        await status['ws_connection'].send(json.dumps({'op': 'heartbeat', 'timestamp': time.time()}))
                        response = await status['ws_connection'].recv()
                        response = json.loads(response.decode("utf-8"))
                        if response['status'] == 'SUCCESS':
                            try:
                                self.bot.children[child]['last_heartbeat'] = response['timestamp']
                            except KeyError:
                                print("EXC", response)
                    except RuntimeError:
                        pass
                    except websockets.exceptions.ConnectionClosedOK:
                        pass
                await asyncio.sleep(5)
    
    async def _dead_connection_reaper(self):
        while True:
            reap = []

            async with self.lock:
                for _, session in self._sessions.items():
                    if isinstance(session, LocalSession):
                        if session._last_track_completion is not None:
                            delta = time.time() - session._last_track_completion
                            if delta > self.bot.conf.lavalink.disconnect_when_inactive_for and session._is_playing is False:
                                reap.append(session)
                        elif time.time() - session.initialization_time > self.bot.conf.lavalink.disconnect_when_inactive_for and session._is_playing is False:
                            reap.append(session)
                for session in reap:
                    await session.send("Disconnecting due to inactivity.")
                    await self.ddestroy_session(session)
                
            await asyncio.sleep(5)
    
    async def _ll_ws_loop(self):
        async with websockets.connect(f"{self.ws_endpoint}/v4/websocket", extra_headers=self.ws_headers) as websocket:
            self._ws_connected = True

            async for message in websocket:
                data = json.loads(message)
                data = cc_to_sc_dict(data)
                await self.websocket_event(data)

    async def websocket_event(self, payload):
        
        op = payload.pop("op")

        if op == "ready":
            self._session_id = payload['session_id']
        
        elif op == "stats":
            self._stats_deque.append(StatsEvent.from_dict(payload))
        
        elif op == "playerUpdate":
            event = PlayerUpdateEvent.from_dict(payload)
            session = await self.get_local_session(int(event.guild_id))

            if session is None:
                return
            
            session._state = event.state
            self._sessions[session.voice_id] = session
            self.loop.create_task(self._sessions[session.voice_id].on_player_update(event))
            return
        else:
            track_events = [TrackStartEvent, TrackEndEvent, TrackExceptionEvent]
            event_type = payload.pop('type', None)
            for event_cls in track_events:
                if event_cls.__name__ == event_type:
                    event = event_cls.from_dict(payload)
                    session = await self.get_local_session(int(event.guild_id))
                    if session is None:
                        return
                    self.loop.create_task(getattr(session, event.callback)(event))
    
    async def handle_ws_recv(self, websocket, payload):
        try:
            await Operation.process(self, websocket, payload)
        except Exception:
            self.bot.logger.error(traceback.format_exc())
    
    async def request(self, method: HttpMethod, route: str, data: dict = {}):
        async with aiohttp.ClientSession() as session:
            async with session.request(method.value, f"{self.rest_endpoint}{route}", headers=self.rest_headers, json=data) as response:
                if method == HttpMethod.DELETE:
                    return
                data = await response.json()
                return cc_to_sc_dict(data)
    
    async def update_player(self, guild_id: int, no_replace: bool=False, data: dict={}):
        data = await self.request(
            HttpMethod.PATCH,
            f"/v4/sessions/{self.session_id}/players/{guild_id}?noReplace={'false' if not no_replace else 'true'}",
            data=data
        )
        if 'timestamp' not in data:
            print(data)
        return Player.from_dict(data)
    
    async def get_player(self, guild_id: int):
        data = await self.request(
            HttpMethod.GET,
            f"/v4/sessions/{self.session_id}/players/{guild_id}",
            data={}
        )
        return Player.from_dict(data)

    async def load_tracks(self, identifier: str):
        result = await self.request(
            HttpMethod.GET,
            f"/v4/loadtracks?identifier={identifier}"
        )

        if result['load_type'] == "track":
            return Track.from_dict(result['data'])
        elif result['load_type'] == "playlst":
            raise ValueError("playlists aren't supported yet :>")
        elif result['load_type'] == "search":
            return list([Track.from_dict(cc_to_sc_dict(data)) for data in result['data']])
        elif result['load_type'] == "empty":
            return None
        else:
            return None

    async def yt_search(self, query: str):
        return await self.load_tracks(f"ytsearch:{query}")

    async def load_or_search_tracks(self, query: str):
        if "http://" in query or "https://" in query:
            return await self.load_tracks(query)
        return await self.yt_search(query)

    def get_stats_embed(self):
        embed = hikari.Embed(title="Lavalink Statistics")
        ratio = self.latest_stats.stats.cpu.system_load
        cpu = generate_volume_bar(int(ratio * 100))
        embed.description = f"`CPU {cpu} {int(ratio * 100)}%`\n"

        ratio = self.latest_stats.stats.memory.used / self.latest_stats.stats.memory.allocated
        memory = generate_volume_bar(int(ratio * 100))
        embed.description += f"`RAM {memory} {int(ratio * 100)}%`\n"
        
        embed.description += "\n```Player Statistics:\n"
        idle = self.latest_stats.stats.players - self.latest_stats.stats.playing_players
        embed.description += f"IDLE ---------- {idle}\n"
        embed.description += f"IN-PLAYBACK --- {self.latest_stats.stats.playing_players}\n"
        embed.description += f"TOTAL --------- {self.latest_stats.stats.players}\n"
        embed.description += "```"
        return embed