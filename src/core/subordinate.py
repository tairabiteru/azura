from core.conf import conf, initLogger
from core.commands import SlashCommandCheckFailure
from core.help import TopicContainer
# from core.subroutines import subroutine
from dash.core import Dash
from orm.revisioning import Revisioning
from orm.member import Member
from orm.server import Server
from ext.utils import localnow
from ext.koe.koe import Koe, KoeEventHandler

import colorlog
import hikari
import json
import lavasnek_rs
import lightbulb
import os
import traceback

import asyncio
import socket
import sys
import os


class Subordinate(lightbulb.Bot):
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
            lava_client = await builder.build(KoeEventHandler())
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
