from core.conf import conf
from ext.utils import strfdelta
from ext.ctx import create_timeout_message
from ext.koe.exceptions import AlreadyConnected, NoVoiceChannel, NoExistingSession, NoAvailableEndpoint, BadResponse

import aiohttp
import asyncio
import datetime
import hikari
import urllib


class KoeBaseSession:
    def __init__(self, gid, vid, cid):
        self.gid = gid
        self.vid = vid
        self.cid = cid


class LocalKoeSession(KoeBaseSession):
    """
    Abstraction of a local Koe session.

    Local sessions are those controlled by the bot in which the session is
    stored and controlled. In other words, a local session is one which is
    possessed by the bot that's responsible for the session's playback.
    """
    def __init__(self, bot, gid, vid, cid):
        self.bot = bot
        self.now_playing_message = None
        self.interactionListenerTask = None
        self._volume = 100
        super().__init__(gid, vid, cid)

    def trackTimeline(self, position, length):
        LENGTH = 40
        percent = position / length
        complete = "=" * int(percent * LENGTH)
        left = "-" * int(LENGTH - (percent * LENGTH))
        timeline = f"[{complete}>{left}]"

        position = datetime.timedelta(seconds=position)
        length = datetime.timedelta(seconds=length)
        position = strfdelta(position, '{%H}:{%M}:{%S}')
        length = strfdelta(length, '{%H}:{%M}:{%S}')
        return f"{position} `{timeline}` {length}"

    async def getNowPlayingEmbed(self, event=None):
        node = await self.bot.lavalink.get_guild_node(self.gid)
        requester = self.bot.cache.get_member(self.gid, node.now_playing.requester)

        embed = hikari.embeds.Embed(
            title=f"{node.now_playing.track.info.title}",
            url=node.now_playing.track.info.uri
        )
        embed.add_field(name="Author", value=node.now_playing.track.info.author, inline=True)
        embed.add_field(name="Requested by", value=requester.username, inline=True)

        embed.add_field(name="Volume", value=f"{self._volume}%", inline=True)

        if event is not None:
            embed.description = self.trackTimeline(event.state_position / 1000, node.now_playing.track.info.length / 1000)

        if "youtube.com" in node.now_playing.track.info.uri:
            url = urllib.parse.urlparse(node.now_playing.track.info.uri)
            query = urllib.parse.parse_qs(url.query)
            embed.set_image(f"https://img.youtube.com/vi/{query['v'][0]}/0.jpg")
        return embed

    async def getActionRow(self, is_paused):
        row = self.bot.rest.build_action_row()
        row.add_button(hikari.ButtonStyle.SECONDARY, "⏮️").set_label("⏮️").add_to_container()
        row.add_button(hikari.ButtonStyle.DANGER, "⏹️").set_label("⏹️").add_to_container()
        pbutton = "▶️" if is_paused else "⏸️"
        row.add_button(hikari.ButtonStyle.SECONDARY, pbutton).set_label(pbutton).add_to_container()
        row.add_button(hikari.ButtonStyle.SECONDARY, "⏭️").set_label("⏭️").add_to_container()
        return row

    async def interactionListener(self):
        try:
            async with self.bot.stream(hikari.InteractionCreateEvent, None).filter(
                lambda event: (
                    isinstance(event.interaction, hikari.ComponentInteraction)
                    and event.interaction.message.id == self.now_playing_message.id
                )
            ) as stream:
                async for event in stream:
                    if event.interaction.custom_id == "⏮️":
                        print("previous")
                    elif event.interaction.custom_id in ["⏸️", "▶️"]:
                        setting = await self.pause()
                        row = await self.getActionRow(setting)
                        await event.interaction.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE, components=[row])
                    elif event.interaction.custom_id == "⏹️":
                        await self.disconnect()
                    elif event.interaction.custom_id == "⏭️":
                        print("skip")
                    elif event.interaction.custom_id == "🔉":
                        await self.volume(self._volume - 5)
                    elif event.interaction.custom_id == "🔊":
                        await self.volume(self._volume + 5)
        except Exception as e:
            print(str(e))

    async def delete(self):
        await self.bot.koe.delSession(self)

    async def stop(self):
        await self.now_playing_message.edit(components=[])

    async def connect(self):
        await self.bot.update_voice_state(self.gid, self.vid)
        info = await self.bot.lavalink.wait_for_full_connection_info_insert(self.gid)
        await self.bot.lavalink.create_session(info)
        await self.bot.koe.addSession(self)
        await create_timeout_message(self.bot, self.cid, "Connected.", 5)

    async def disconnect(self):
        await self.stop()
        await self.delete()
        await self.bot.lavalink.destroy(self.gid)
        await self.bot.update_voice_state(self.gid, None)
        await self.bot.lavalink.wait_for_connection_info_remove(self.gid)
        await self.bot.lavalink.remove_guild_node(self.gid)
        await self.bot.lavalink.remove_guild_from_loops(self.gid)
        await create_timeout_message(self.bot, self.cid, "Disconnected.", 5)

        if self.bot.name != conf.name:
            data = {'vid': self.vid}
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://{conf.dash.host}:{conf.dash.port}/api/session/delete", json=data, headers={'Content-Type': 'application/json'}) as response:
                    resp = await response.json()

    async def play(self, uid, query):
        track = await self.bot.lavalink.auto_search_tracks(query)
        track = track.tracks[0]
        await self.bot.lavalink.play(self.gid, track).requester(uid).queue()

    async def pause(self, setting="toggle"):
        if setting == "toggle":
            node = await self.bot.lavalink.get_guild_node(self.gid)
            if node.is_paused:
                setting = False
            else:
                setting = True
        await self.bot.lavalink.set_pause(self.gid, setting)
        return setting

    async def volume(self, setting):
        self._volume = setting
        await self.bot.lavalink.volume(self.gid, setting)


class ChildKoeSession(LocalKoeSession):
    """
    Abstraction of a Koe child local session.

    In contrast of both RemoteKoeSession and LocalKoeSession,
    ChildKoeSession can only be possessed by children of the parent.
    It largely inherits methods from LocalKoeSession, though disconnect
    must be handled differently so as to inform the parent of the session
    removal.
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
    Abstraction of a remote Koe session.

    Remote sessions are those NOT controlled by the bot in which the session is
    stored and controlled. Remote sessions should *in theory* only be able to
    be possessed by the master bot.
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
        return resp

    async def delete(self):
        data = self.serialize()
        await self.post("/api/session/delete", data)

    async def connect(self):
        data = self.serialize()
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


class KoeEventHandler:
    def __init__(self, bot, *args, **kwargs):
        self.bot = bot

    async def player_update(self, lavalink, event):
        session = await self.bot.koe.fromGuild(event.guild_id)
        if session.now_playing_message is not None:
            embed = await session.getNowPlayingEmbed(event=event)
            await session.now_playing_message.edit(embed)

    async def track_start(self, lavalink, event):
        session = await self.bot.koe.fromGuild(event.guild_id)
        session.now_playing_message = None
        embed = await session.getNowPlayingEmbed()

        row1 = self.bot.rest.build_action_row()
        row1.add_button(hikari.ButtonStyle.SECONDARY, "⏮️").set_label("⏮️").add_to_container()
        row1.add_button(hikari.ButtonStyle.DANGER, "⏹️").set_label("⏹️").add_to_container()
        row1.add_button(hikari.ButtonStyle.SECONDARY, "⏸️").set_label("⏸️").add_to_container()
        row1.add_button(hikari.ButtonStyle.SECONDARY, "⏭️").set_label("⏭️").add_to_container()

        session.now_playing_message = await self.bot.rest.create_message(session.cid, embed, components=[row1])
        loop = hikari.internal.aio.get_or_make_loop()
        session.interactionListenerTask = loop.create_task(session.interactionListener())

        conf.logger.debug(f"Track started in guild: {event.guild_id}.")

    async def track_finish(self, lavalink, event):
        session = await self.bot.koe.fromGuild(event.guild_id)
        if session:
            await session.stop()
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
