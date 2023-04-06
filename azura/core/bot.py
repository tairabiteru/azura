from core.conf import conf
from dash.core import Dash
from orm.connector import ORM
from ext.utils import utcnow, strfdelta

import orm.models as models

import aiohttp
import enum
import hikari
import keikou
import koe
import lavasnek_rs
import lightbulb
import logging
import miru
import os
import pytz
import tortoise

"""
--- IMPORTANT ---

Make it so when Azura is idle in a channel for a certain amount of time, she
at random intervals, plays the intro riff from "bad to the bone"
"""


class BotType(enum.Enum):
    PARENT = "PARENT"
    CHILD = "CHILD"


class Bot(lightbulb.BotApp):
    def __init__(self, name=None, *args, **kwargs):
        self.name = name if name is not None else conf.get_parent().name
        self.conf = conf.get_bot(self.name)
        self.lavalink = None
        self.dash = None
        self.permissions = None
        self.revision = None
        self.koe = koe.Koe(self)

        logging.root.setLevel(logging.NOTSET)
        self.logger = logging.getLogger(self.name)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(name)s][%(levelname)s] %(message)s'))
        self.logger.addHandler(handler)

        kwargs['token'] = self.conf.token
        kwargs['logs'] = conf.hikari_loglevel if conf.hikari_loglevel else None
        kwargs['intents'] = hikari.Intents.ALL
        super().__init__(*args, **kwargs)

        miru.load(self)

        if self.type is BotType.PARENT:
            self.load_extensions("cogs.admin")
            self.load_extensions("cogs.issues")
            self.load_extensions("cogs.music")
            self.load_extensions("cogs.playlist")

        self.subscribe(hikari.ShardReadyEvent, self.on_ready)
        self.subscribe(hikari.VoiceStateUpdateEvent, self.on_voice_state_update)
        self.subscribe(hikari.VoiceServerUpdateEvent, self.on_voice_server_update)

    @property
    def type(self):
        if self.conf.is_parent is True:
            return BotType.PARENT
        return BotType.CHILD
    
    async def post(self, endpoint, path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{endpoint}{path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                response = await response.json()
        return response

    async def close_database(self):
        self.logger.warning("Closing ORM connections...")
        await ORM.close_connections()

    async def shutdown(self):
        await self.close_database()
        self.logger.warning("ORM connections closed. Shutting down. Bye!")
        os.system(f"touch {os.path.join(conf.rootDir, 'lock')}")
        await self.close()

    async def reinit(self, channel):
        if self.type is BotType.PARENT:
            await self.reinit_children()

        await models.OpVars.set_for_reinit(channel)
        await self.close_database()
        self.logger.warning("ORM connections closed. Restarting, brb!")
        await self.close()

    def initialize_children(self):
        if self.type is not BotType.PARENT:
            raise ValueError(f"{self.name} is not the parent bot.")

        for bot in conf.bots:
            if bot.is_parent is False:
                self.logger.info(f"Initializing child bot {bot.name}...")
                os.system(f"python3.9 azura --name {bot.name} --multiplex")
    
    async def reinit_children(self):
        if self.type is not BotType.PARENT:
            raise ValueError(f"{self.name} is not the parent bot.")
        
        for bot in conf.bots:
            if bot.is_parent is False:
                self.logger.info(f"Reinitializing child bot {bot.name}...")
                try:
                    await self.post(f"http://{bot.host}:{bot.port}", "/api/reinitialize", {})
                    self.logger.info(f"{bot.name} responded to reinitialization call.")
                except aiohttp.client_exceptions.ClientConnectorError:
                    self.logger.warning(f"{bot.name} did not respond to reinitialization call.")
    
    async def reinit_individual(self, child, report_to=None):
        if self.type is not BotType.PARENT:
            raise ValueError(f"{self.name} is not the parent bot.")
        
        for bot in conf.bots:
            if bot.name.lower() == child.lower():
                break
        else:
            raise ValueError(f"`{self.name}` is not the name of any of my children.")
        
        if bot.is_parent:
            await models.OpVars.set_for_reinit(report_to)
            await self.close_database()
            self.logger.warning("ORM connections closed. Restarting, brb!")
            await self.close()

        self.logger.info(f"Reinitializing child bot {bot.name}...")
        try:
            await self.post(f"http://{bot.host}:{bot.port}", "/api/reinitialize", {})
            self.logger.info(f"{bot.name} responded to reinitialization call.")
        except aiohttp.client_exceptions.ClientConnectorError:
            self.logger.warning(f"{bot.name} did not respond to reinitialization call.")

    async def on_ready(self, event):
        self.logger.info("Initializing ORM connection...")
        try:
            await ORM.init(self, config=conf.orm_config, _create_db=True)
            await ORM.generate_schemas()
        except tortoise.exceptions.OperationalError:
            await ORM.init(self, config=conf.orm_config)
            await ORM.generate_schemas(safe=True)

        if self.type.value == "PARENT":
            self.revision = await models.Revision.calculate()
        else:
            self.revision = await models.Revision.latest()

        self.logger.info("Initializing permissions manager...")
        self.permissions = keikou.PermissionsManager(self)
        self.logger.info("Building help topics...")
        self.help = keikou.HelpTopic(self)

        self.logger.info("Initializing lavalink connection...")
        builder = lavasnek_rs.LavalinkBuilder(event.my_user.id, "")
        builder.set_host(conf.lavalink.host)
        builder.set_password(conf.lavalink.password)
        builder.set_start_gateway(False)
        lava_client = await builder.build(koe.EventHandler(self))
        self.lavalink = lava_client

        self.logger.info("Initializing dashboard...")
        self.dash = Dash(self)
        loop = hikari.internal.aio.get_or_make_loop()
        loop.create_task(self.dash.run())

        if self.type is BotType.PARENT:
            opvars = await models.OpVars.get()
            if opvars.reinit_timestamp is not None:
                elapsed = utcnow() - opvars.reinit_timestamp
                timestamp = opvars.reinit_timestamp.astimezone(pytz.timezone(conf.timezone))
                await self.rest.create_message(
                    opvars.reinit_channel,
                    f"✔️ Reinitialization completed after {strfdelta(elapsed, '{%M}:{%S}')}, current version is {self.revision.version}.",
                )
                self.logger.info(f"Reinitialization call at {timestamp.strftime('%m/%d/%Y %H:%M:%S')} completed. Time elapsed was {strfdelta(elapsed, '{%M}:{%S}')}")
                await models.OpVars.clear_for_reinit()
            else:
                self.logger.info("Initialization completed successfully.")

        self.logger.info(f"API contact, {self.name.capitalize()} is now online.")

    async def on_voice_state_update(self, event):
        await self.koe.handle_voice_state_update(event)
        self.lavalink.raw_handle_event_voice_state_update(
            event.state.guild_id,
            event.state.user_id,
            event.state.session_id,
            event.state.channel_id
        )

    async def on_voice_server_update(self, event):
        await self.lavalink.raw_handle_event_voice_server_update(
            event.guild_id,
            event.endpoint,
            event.token
        )
