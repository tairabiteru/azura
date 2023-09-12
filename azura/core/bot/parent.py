from .base import BaseBot
from .child import ChildBot
from ..conf.loader import conf
from ..console import console
from ...mvc.core.server import UvicornServer
from ...mvc.discord.hooks import DiscordEventHandler
from ...mvc.internal.models import OperationalVariables, Revision, Child
from ...ext.utils import utcnow, strfdelta, port_in_use
from ...ext.ctx import ReinitEmbed
from ...ext.daemon import Daemon
import azura.keikou as keikou

import asyncio
import hikari
import logging
import multiprocessing
import uvicorn
import orjson as json
import os
import time
import websockets
from django.core.management import execute_from_command_line


def construct_and_run(conf, parent_ws_uri):
    child = ChildBot(conf, parent_ws_uri)
    child.run()


class ParentBot(BaseBot):
    def __init__(self, conf, *args, **kwargs):
        self.print_banner("azura", True, False)
        super().__init__(conf, *args, **kwargs)

        self.daemons = []

        uvicorn.config.LOGGING_CONFIG['formatters']['default']['fmt'] = conf.logging.log_format
        uvicorn.config.LOGGING_CONFIG['formatters']['default']['use_colors'] = True
        uvicorn.config.LOGGING_CONFIG['formatters']['access']['fmt'] = conf.logging.log_format
        uvicorn.config.LOGGING_CONFIG['formatters']['access']['use_colors'] = True
        uvicorn.config.LOGGING_CONFIG['handlers']['file'] = {
            'formatter': 'access',
            '()': lambda: logging.handlers.TimedRotatingFileHandler(os.path.join(conf.logs, "access.log"), when="midnight"),
            }
        uvicorn.config.LOGGING_CONFIG['loggers']['uvicorn.access']['handlers'] = ["file"]

        self.uvicorn = None
        self.children = {}

        super().load_extensions_from("azura/plugins")

        self.subscribe(hikari.GuildEvent, DiscordEventHandler.handle_guild_event)
        self.subscribe(hikari.MemberEvent, DiscordEventHandler.handle_member_event)
        self.subscribe(hikari.ChannelEvent, DiscordEventHandler.handle_channel_event)
        self.subscribe(hikari.RoleEvent, DiscordEventHandler.handle_role_event)
    
    @property
    def child_connections(self):
        connections = {}
        for name, status in self.children.items():
            if status['is_alive'] is True:
                connections[name] = status['ws_connection']
        return connections
    
    async def kill(self, sender=None, channel=None):
        if sender is None:
            self.logger.warning("Kill signal received, shutting down.")
        else:
            self.logger.warning(f"Kill signal sent by {sender.username}, shutting down.")

        f = open(os.path.join(conf.root, "lock"), "w")
        f.close()

        if self.uvicorn is not None:
            await self.uvicorn.shutdown(self)
        await self.stop_miru()
        await self.hanabi.stop()
        await self.stop_children()
        await self.close()
    
    async def reinit(self, sender=None, channel=None, message=None):
        if sender is None:
            self.logger.warning("Reinit signal received, restarting.")
        else:
            self.logger.warning(f"Reinit signal received from {sender.username}, restarting.")
        await OperationalVariables.set_for_reinit(channel=channel, message=message)

        if self.uvicorn is not None:
            await self.uvicorn.shutdown(self)
        await self.stop_miru()
        await self.stop_children()
        await self.close()
    
    async def post_init(self):
        version = await Revision.calculate()
        self.logger.info(f"Calculated version is {version.full_version}")

        problems = False
        try:
            await self.rest.fetch_user(self.conf.owner_id)
        except hikari.errors.NotFoundError:
            problems = True
            self.logger.warn(f"The owner ID {self.conf.owner_id} is not a valid Discord UID.")
        
        if not problems:
            self.logger.info("No issues found in post-initialization configuration check.")
        
        opvars = await OperationalVariables.aget()
        if opvars.reinit_timestamp is not None:
            elapsed = utcnow() - opvars.reinit_timestamp
            timestamp = opvars.reinit_timestamp.astimezone(self.timezone)
            version = await self.get_version()
            message = f"Reinitialization call at {timestamp.strftime('%x %X %Z')} completed. Time elapsed was {strfdelta(elapsed, '{%M}:{%S}')}.\n"
            message += f"Initialized into {version}."
            channel = (await OperationalVariables.objects.select_related('reinit_channel').aget(id=1)).reinit_channel
            if channel is not None:
                if opvars.reinit_message is None:
                    await self.rest.create_message(channel.id, f"{message}")
                else:
                    m = await self.rest.fetch_message(channel.id, opvars.reinit_message)
                    await m.edit("", embed=ReinitEmbed("post", details=f"{message}"))
            await OperationalVariables.clear_for_reinit()
        else:
            self.logger.info("Initialization completed successfully.")

        loop = hikari.internal.aio.get_or_make_loop()
        loop.create_task(console(self, loop))
    
    async def start_http(self):
        if port_in_use(self.conf.mvc.port):
            self.logger.warning(f"Failed to start HTTP daemon on port {self.conf.mvc.port}: it is already in use.")
            return

        execute_from_command_line(["", "collectstatic", "--noinput"])

        loop = hikari.internal.aio.get_or_make_loop()
        loop.bot = self
        config = uvicorn.Config(
            "azura.mvc.core.asgi:application",
            host=self.conf.mvc.host,
            port=self.conf.mvc.port,
            log_level=self.conf.logging.mvc_level.lower(),
            loop=loop
        )
        self.uvicorn = UvicornServer(config)
        loop.create_task(self.uvicorn.serve())

        self.logger.info(f"Started internal webserver on {self.conf.mvc.host}:{self.conf.mvc.port}.")

    def add_daemon(self, daemon):
        self.daemons.append(daemon)
    
    def run_daemons(self):
        loop = hikari.internal.aio.get_or_make_loop()
        for d in [d() for d in Daemon.ALL]:
            d.attach_bot(self)
            loop.create_task(d.service())
    
    def get_child_connection(self, child):
        return self.child_connections[child]
    
    async def send_to_child(self, child, data):
        return await self.get_child_connection(child).send(data)
    
    async def wait_for_children_init(self, timeout=10):
        start = time.time()
        while time.time() - start < timeout:
            all_alive = True

            for child, status in self.children.items():
                if status['is_alive'] is False:
                    all_alive = False
            
            if all_alive is True:
                return
            await asyncio.sleep(0.05)
        raise asyncio.TimeoutError("Operation timed out.")
    
    async def init_children(self):
        multiprocessing.set_start_method("spawn")

        async for child in Child.objects.all():
            child_conf = child.construct_config(self.conf)
            child = multiprocessing.Process(target=construct_and_run, args=(child_conf, self.websocket_addr))
            self.children[child_conf.name] = {}
            self.children[child_conf.name]['process'] = child
            self.children[child_conf.name]['is_alive'] = False
            self.children[child_conf.name]['ws_uri'] = f"ws://{child_conf.lavalink.websocket_host}:{child_conf.lavalink.websocket_port}"
            self.children[child_conf.name]['last_heartbeat'] = None
            child.start()
        await self.wait_for_children_init()
        self.logger.info("All children online.")
    
    async def stop_children(self):
        for child, status in self.children.items():
            connection = status['ws_connection']
            try:
                await connection.send(json.dumps({'op': 'shutdown'}))
            except websockets.exceptions.ConnectionClosedOK:
                continue
    
    async def on_ready(self, event):
        self._last_connection = self.localnow()
        self.logger.info(f"API contact, {self.conf.name} is online.")
        self.logger.info(f"Initialization took {(self.last_connection - self.last_instantiation).total_seconds()} seconds.")
        self.attach_signal_handlers()
        loop = hikari.internal.aio.get_or_make_loop()
        loop.create_task(self._self_ws_loop())
    
        if self.conf.mvc.enable_http:
            await self.start_http()
        
        self._permissions = keikou.PermissionsManager(self)
        self._help = keikou.HelpTopic(self)
        await self._help.initialize()

        await DiscordEventHandler.run_model_update(self)
        await self.start_hanabi()
        await self.init_children()
    
        self.run_daemons()

        self.full_init_complete.set()
        await self.post_init()