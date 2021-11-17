from core.conf import conf
from ext.koe.exceptions import AlreadyConnected, NoVoiceChannel, NoExistingSession, NoAvailableEndpoint, BadResponse

import aiohttp
import asyncio
import hikari


class KoeSession:
    def __init__(self, endpoint, gid, vid, uid):
        self.endpoint = endpoint
        self.gid = gid
        self.vid = vid
        self.uid = uid

    async def post(self, api_path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}{api_path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                return await response.json()

    async def connect(self, koe):
        data = {'gid': self.gid, 'vid': self.vid}
        data = await self.post("/api/voice/connect", data)
        if data['response'] == 'success':
            await koe.addSession(self)
        else:
            raise BadResponse(data)

    async def disconnect(self, koe):
        data = {'gid': self.gid}
        data = await self.post("/api/voice/disconnect", data)
        if data['response'] == 'success':
            await koe.delSession(self)
        else:
            raise BadResponse(data)

    async def play(self, koe, uid, query):
        data = {'gid': self.gid, 'uid': uid, 'query': query}
        return await self.post("/api/voice/play", data)


class Koe:
    def __init__(self, bot):
        self.bot = bot
        self._sessions = {}
        self._lock = asyncio.Lock()
        self.webcon: aiohttp.ClientSession = None

    async def initialize(self):
        self.webcon = aiohttp.ClientSession()

    async def addSession(self, session):
        async with self._lock:
            for gid, s in self._sessions.items():
                if session.gid == gid:
                    raise AlreadyConnected(session.gid, s.vid)

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

    async def fromCTX(self, ctx, connect=True, must_exist=False):
        return await self.fromComponents(ctx.guild_id, ctx.author.id, connect=connect, must_exist=must_exist)

    async def fromComponents(self, gid, uid, connect=True, must_exist=False):
        vid = await self.vidFromUser(uid)
        async with self._lock:
            try:
                return self._sessions[vid]
            except KeyError:
                if must_exist is True:
                    raise NoExistingSession(vid)
                endpoint = await self.getNewEndpoint(gid)
                session = KoeSession(endpoint, gid, vid, uid)

        if connect is True:
            await session.connect(self)
        return session

    async def voiceView(self):
        states = []
        for gid, vs in self.bot.cache.get_voice_states_view().items():
            for uid, state in vs.items():
                if uid == self.bot.get_me().id:                              # to be replaced by lavalink playing status
                    states.append({'gid': int(gid), 'vid': state.channel_id, 'status': 'in use'})
        return states

    @property
    def api_ports(self):
        ports = []
        for port in range(conf.dash.port, conf.dash.port + len(conf.subordinate_tokens) + 1):
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

    async def getNewEndpoint(self, gid):
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


class KoeEventHandler:

    async def track_start(self, _lava_client, event):
        conf.logger.debug(f"Track started in guild: {event.guild_id}.")

    async def track_finish(self, lavalink, event):
        conf.logger.debug(f"Track finished in guild: {event.guild_id}.")

    async def track_exception(self, lavalink, event):
        conf.logger.warning(f"Track exception happened in guild: {event.guild_id}.")

        skip = await lavalink.skip(event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)

        if not skip:
            await event.message.respond("Nothing to skip")
        else:
            if not node.queue and not node.now_playing:
                await lavalink.stop(event.guild_id)
