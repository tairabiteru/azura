from ..conf.loader import conf
from ...mvc.internal.models import Revision
from ...ext.utils import utcnow, aio_get

import azura.keikou as keikou
import azura.hanabi as hanabi

import asyncio
import hikari
import lightbulb
import miru
import colorlog
import logging
import orjson as json
import os
import traceback
import zoneinfo
import signal
import websockets


class BaseBot(lightbulb.BotApp):
    def __init__(self, conf, *args, **kwargs):
        self.conf = conf
        self.full_init_complete = asyncio.Event()

        logging.root.setLevel(logging.NOTSET)

        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(self.conf.logging.main_level)
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                f"%(log_color)s[{self.conf.name}]{self.conf.logging.log_format}",
                datefmt=self.conf.logging.date_format,
                reset=True,
                log_colors={
                    'DEBUG': "light_blue",
                    'INFO': conf.log_color,
                    'WARNING': "light_yellow",
                    'ERROR': "light_red",
                    'CRITICAL': "light_purple"
                }
            )
        )

        file_handler = logging.handlers.TimedRotatingFileHandler(
            os.path.join(self.conf.logs, f"{self.conf.name.lower()}.log"),
            when="midnight"
        )
        file_handler.setLevel(self.conf.logging.main_level)
        file_handler.setFormatter(
            logging.Formatter(f"[{self.conf.name}]{self.conf.logging.log_format}")
        )

        self.logger = colorlog.getLogger()
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

        self.last_instantiation = self.localnow()
        self._last_connection = None

        self._permissions = None
        self._help = None
        self._ws_server = None
        self.hanabi = None

        kwargs['token'] = self.conf.token
        kwargs['prefix'] = self.conf.prefix
        kwargs['logs'] = self.conf.logging.main_level
        kwargs['intents'] = hikari.Intents.ALL
        kwargs['help_class'] = None
        kwargs['banner'] = None

        super().__init__(*args, **kwargs)
        miru.install(self)

        self.subscribe(hikari.ShardReadyEvent, self.on_ready)
        self.subscribe(keikou.CommandErrorEvent, self.on_command_error)
        self.subscribe(hikari.VoiceStateUpdateEvent, self.on_voice_state_update)
        self.subscribe(hikari.VoiceServerUpdateEvent, self.on_voice_server_update)
    
    @property
    def permissions(self):
        if self._permissions is None:
            raise ValueError("Keikou permissions manager is not initialized.")
        return self._permissions
    
    @property
    def help(self):
        if self._help is None:
            raise ValueError("Keikou help manager is not initialized.")
        return self._help
    
    async def get_version(self):
        return (await Revision.objects.alatest()).full_version
    
    @property
    def last_connection(self):
        if self._last_connection is None:
            raise ValueError("This instance does not have any recorded API contact.")
        return self._last_connection
    
    @property
    def timezone(self):
        return zoneinfo.ZoneInfo(self.conf.timezone)
    
    @property
    def domain(self):
        return conf.mvc.allowed_hosts[0]

    @property
    def websocket_addr(self):
        return f"ws://{self.conf.lavalink.websocket_host}:{self.conf.lavalink.websocket_port}"
    
    def localnow(self):
        return utcnow().astimezone(self.timezone)
    
    async def get_public_ip(self):
        return await aio_get("https://api4.my-ip.io/ip")
    
    def attach_signal_handlers(self):
        loop = hikari.internal.aio.get_or_make_loop()
        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(getattr(signal, signame), lambda: asyncio.create_task(self.kill()))
    
    async def kill(self, sender=None, channel=None):
        if sender is None:
            self.logger.warning("Kill signal received, shutting down.")
        else:
            self.logger.warning(f"Kill signal sent by {sender.username}, shutting down.")

        await self.stop_miru()
        await self.hanabi.stop()
        self._ws_server.close()
        await self.close()
    
    async def reinit(self, sender=None, channel=None, message=None):
        if sender is None:
            self.logger.warning("Reinit signal received, restarting.")
        else:
            self.logger.warning(f"Reinit signal received from {sender.username}, restarting.")

        await self.stop_miru()
        await self.hanabi.stop()
        self._ws_server.close()
        await self._ws_server.wait_closed()
        await self.close()
    
    async def post_init(self):
        self.logger.info("Initialization completed successfully.")
    
    async def stop_miru(self):
        # List call made to create a copy, otherwise dict changes size during iteration
        try:
            for view in list(miru.View._events._bound_handlers.values()):
                if view.message is not None:
                    try:
                        await view.message.edit(components=[])
                    except hikari.NotFoundError:
                        pass
                view.stop()
            miru.uninstall()
        except AttributeError:
            pass
    
    async def start_hanabi(self):
        self.hanabi = hanabi.Hanabi(
            self,
            host=conf.lavalink.host,
            port=conf.lavalink.port,
            password=conf.lavalink.password,
            user_id=self.get_me().id,
            loop=hikari.internal.aio.get_or_make_loop()
        )
        self.hanabi.start()
    
    def available_in(self, guild_id):
        for guild, state in self.cache.get_voice_states_view_for_guild(guild_id).items():
            if state.user_id == self.get_me().id:
                return False
        return True
    
    def run(self, *args, **kwargs):
        try:
            return super().run(*args, *kwargs)
        except hikari.errors.UnauthorizedError:
            self.logger.critical("Invalid or missing Discord token.")
            self.logger.critical("Shutting down...")

    async def on_voice_state_update(self, event):
        if self.hanabi is not None:
            await self.hanabi.handle_voice_state_update(
                event.state.user_id,
                event.state.guild_id,
                event.state.session_id,
                event.state.channel_id
            )

    async def on_voice_server_update(self, event):
        if self.hanabi is not None:
            await self.hanabi.handle_voice_server_update(
                event.guild_id,
                event.endpoint,
                event.token
            )
    
    async def on_websocket_recv(self, websocket, message):
        await self.hanabi.handle_ws_recv(websocket, json.loads(message))
    
    async def _self_ws_loop(self):
        async def handler(websocket):
            async for message in websocket:
                await self.on_websocket_recv(websocket, message)

        self._ws_server = await websockets.serve(
            handler,
            self.conf.lavalink.websocket_host,
            self.conf.lavalink.websocket_port,
            start_serving=False
        )
        await self._ws_server.start_serving()
    
    async def on_ready(self, event):
        self._last_connection = self.localnow()
        self.logger.info(f"API contact, {self.conf.name} is online.")
        self.logger.info(f"Initialization took {(self.last_connection - self.last_instantiation).total_seconds()} seconds.")
        self.attach_signal_handlers()
        loop = hikari.internal.aio.get_or_make_loop()
        loop.create_task(self._self_ws_loop())
        
  
        self._permissions = keikou.PermissionsManager(self)
        self._help = keikou.HelpTopic(self)
        await self._help.initialize()
        await self.start_hanabi()

        self.full_init_complete.set()
        await self.post_init()

    async def on_command_error(self, event):
        if isinstance(event.exception, keikou.CommandInvocationError):
            try:
                await event.context.respond(f"An error occurred during the invocation of `{event.context.command.name}`. Please contact my maintainer about this.")
            except hikari.errors.NotFoundError:
                pass
            raise event.exception.__cause__

        exception = event.exception.__cause__ or event.exception

        if isinstance(exception, keikou.CheckFailure):
            return await exception.send_response()

        try:
            raise exception
        except Exception:
            self.logger.error(traceback.format_exc())