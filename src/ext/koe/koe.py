from core.conf import conf
from ext.koe.session import LocalKoeSession, RemoteKoeSession
from ext.koe.exceptions import AlreadyConnected, NoExistingSession, NoAvailableEndpoint

import aiohttp
import asyncio


class Koe:
    """
    Create a Koe instance.

    Koe effectively acts as a session manager for a given bot. Koe is
    responsible for adding, deleteing, and creating sessions. Each bot
    has its own Koe instance, but only the master bot has a Koe instance
    which can contain RemoteKoeSessions. In this way, the master bot
    effectively acts as a proxy for LocalKoeSessions in other Koe instances
    in the child bots.
    """
    def __init__(self, bot):
        self.bot = bot
        self._sessions = {}
        self._lock = asyncio.Lock()
        self.webcon: aiohttp.ClientSession = None

    async def initialize(self):
        self.webcon = aiohttp.ClientSession()

    async def addSession(self, session):
        async with self._lock:
            for vid, s in self._sessions.items():
                if session.vid == vid:
                    raise AlreadyConnected(session.vid, s.vid)

            self._sessions[session.vid] = session

    async def delSession(self, session):
        async with self._lock:
            del self._sessions[session.vid]

    async def vidFromUser(self, uid):
        for gid, guild in self.bot.cache.get_guilds_view().items():
            states = self.bot.cache.get_voice_states_view_for_guild(guild)
            vs = [s async for s in states.iterator().filter(lambda i: i.user_id == uid)]

            if vs:
                return vs[0].channel_id
        return None

    async def fromCTX(self, ctx, connect=False, must_exist=False):
        vid = await self.vidFromUser(ctx.author.id)
        return await self.fromComponents(ctx.guild_id, ctx.channel_id, vid, connect=connect, must_exist=must_exist)

    async def fromGuild(self, gid):
        async with self._lock:
            for vid, session in self._sessions.items():
                if session.gid == gid:
                    return session

    async def fromComponents(self, gid=None, cid=None, vid=None, connect=False, must_exist=False):
        async with self._lock:
            try:
                return self._sessions[vid]
            except KeyError:
                if must_exist is True:
                    raise NoExistingSession(vid)
                endpoint = await self.getOpenEndpoint(gid)
                if endpoint == self.endpoint:
                    session = LocalKoeSession(self.bot, gid, vid, cid)
                else:
                    session = RemoteKoeSession(self.bot, endpoint, gid, vid, cid)

        if connect is True:
            await session.connect(self)
            await self.addSession(session)
        return session

    async def voiceView(self):
        states = []
        for gid, vs in self.bot.cache.get_voice_states_view().items():
            for uid, state in vs.items():
                if uid == self.bot.get_me().id:                              # to be replaced by lavalink playing status
                    states.append({'gid': int(gid), 'vid': state.channel_id, 'status': 'in use'})
        return states

    @property
    def endpoint(self):
        return f"http://{conf.dash.host}:{self.bot.api_port}"

    @property
    def api_ports(self):
        ports = []
        for port in range(conf.dash.port, conf.dash.port + len(conf.child_tokens) + 1):
            ports.append(port)
        return ports

    @property
    def api_endpoints(self):
        endpoints = []
        for port in self.api_ports:
            endpoints.append(f"http://{conf.dash.host}:{port}")
        return endpoints

    async def allVoiceViews(self):
        resp = {}
        for endpoint in self.api_endpoints:
            async with self.webcon.get(f"{endpoint}/api/voice/states", headers={'Content-Type': 'application/json'}) as response:
                resp[endpoint.split(":")[-1]] = await response.json()
        return resp

    async def getOpenEndpoint(self, gid):
        for endpoint in self.api_endpoints:
            async with self.webcon.get(f"{endpoint}/api/voice/states", headers={'Content-Type': 'application/json'}) as response:
                data = await response.json()
                if data['states'] == []:
                    return endpoint

                if gid not in [state['gid'] for state in data['states']]:
                    return endpoint

                state = list(filter(lambda s: s['gid'] == gid, data['states']))[0]
                if state['status'] == 'available':
                    return endpoint

        raise NoAvailableEndpoint(gid)
