from core.conf import conf
from dash.core import Dash
from ext.utils import localnow
from ext.koe.koe import Koe
from ext.koe.events import KoeEventHandler

import aiohttp
import asyncio
import hikari
import lavasnek_rs
import lightbulb
import os


class Child(lightbulb.Bot):
    def __init__(self, name, port, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.name: str = name
        self.api_port: int = port
        self.token: str = kwargs['token']
        self.lavalink: lavasnek_rs.Lavalink = None
        self.koe: Koe = Koe(self)

        self.last_initalization = localnow()
        self.subscribe(hikari.ShardReadyEvent, self.on_ready)
        self.subscribe(hikari.VoiceStateUpdateEvent, self.on_voice_state_update)
        self.subscribe(hikari.VoiceServerUpdateEvent, self.on_voice_server_update)

    async def cycleState(self, kill=False):
        call = "Kill" if kill is True else "Reinit"
        conf.logger.warning(f"{call} call made. Shutting down...")
        # allow final transmission
        await asyncio.sleep(1)
        if kill is True:
            lockfile = f"{self.name}.lock"
            os.system(f"touch {os.path.join(conf.rootDir, lockfile)}")
        await self.close()

    async def on_ready(self, event) -> None:
        self.last_api_connection = localnow()
        conf.logger.info(f"API contact, {self.name} is online.")

        await self.koe.initialize()

        if conf.dash.enabled:
            self.dash = Dash(self, self.api_port, name=self.name)
            loop = hikari.internal.aio.get_or_make_loop()
            loop.create_task(self.dash.run())

        if conf.audio.lavalink_enabled:
            builder = (
                lavasnek_rs.LavalinkBuilder(self.get_me().id, self.token)
                .set_host(conf.audio.lavalink_addr)
                .set_password(conf.audio.lavalink_pass)
            )
            builder.set_start_gateway(False)
            lava_client = await builder.build(KoeEventHandler(self))
            self.lavalink = lava_client

    async def on_voice_state_update(self, event) -> None:
        await self.lavalink.raw_handle_event_voice_state_update(
            event.state.guild_id,
            event.state.user_id,
            event.state.session_id,
            event.state.channel_id
        )

    async def on_voice_server_update(self, event) -> None:
        await self.lavalink.raw_handle_event_voice_server_update(
            event.guild_id, event.endpoint, event.token
        )


class ChildConnector:
    def __init__(self, name, port):
        self.name = name
        self.port = port

    @property
    def endpoint(self):
        return f"http://{conf.dash.host}:{self.port}"

    def serialize(self):
        return {'gid': self.gid, 'vid': self.vid, 'cid': self.cid}

    def start(self):
        if int(os.system(f"screen -list | awk '{{print $1}}' | grep -q {self.name}$")) == 0:
            conf.logger.info(f"{self.name} is already running.")
            return 1
        else:
            conf.logger.info(f"Starting {self.name}.")
            path = os.path.join(conf.binDir, f"{self.name}.sh")
            os.system(f"screen -S {self.name} -d -m {path}")
            return 0

    async def post(self, api_path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}{api_path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                return await response.json()

    async def reinit(self):
        await self.post("/api/bot/reinit", {})

    async def kill(self):
        await self.post("/api/bot/kill", {})
