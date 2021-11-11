"""
Define bot class and initialize the bot.

This file serves sort of as the beginning point of the bot, as well as the
global subroutine registry.
"""

from core.conf import conf
from core.commands import SlashCommandCheckFailure
from core.help import TopicContainer
# from core.subroutines import subroutine
from dash.core import Dash
from orm.revisioning import Revisioning
from orm.member import Member
from orm.server import Server
from ext.vox import Vox, VoxEventHandler
from ext.execution import codeBlockCheck
from ext.utils import localnow

import hikari
import json
import lavasnek_rs
import lightbulb
import os
import traceback


class Bot(lightbulb.Bot):
    """
    Define *my* bot.

    The default bot provided by lightbulb doesn't quite meet all of the needs I
    have. This subclass provides a bot which properly performs revisioning,
    as well as initializes a dashboard and allows for subroutines.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        revisioning = Revisioning.obtain()
        logoutput = revisioning.calculate()
        conf.logger.debug(logoutput)
        self.version = str(revisioning.current)
        self.subroutines = []
        self.lavalink = None
        self.dash = None

        self.last_initalization = localnow()

    def add_subroutine(self, subroutine):
        self.subroutines.append(subroutine)

    def start_subroutines(self):
        loop = hikari.internal.aio.get_or_make_loop()
        conf.logger.debug("Starting subroutines...")
        for sub in [s() for s in self.subroutines]:
            loop.create_task(sub.task())
            conf.logger.debug(
                f"Started subroutine '{sub.function.__name__}' with a period of {'{:,}'.format(sub.seconds)} seconds."
            )
        conf.logger.debug("Subroutine initialization complete.")

    def halt_subroutine(self, subroutine):
        pass

    def getSlashCommand(self, node):
        for command in self.slash_commands:
            if command.node == node:
                return command

            try:
                for subcommand in command._subcommands.values():
                    if subcommand.node == node:
                        return subcommand
            except AttributeError:
                pass


hikari_loglevel = conf.hikari_loglevel if conf.hikari_loglevel else None
bot = Bot(token=conf.token, prefix=conf.prefix, logs=hikari_loglevel, intents=hikari.Intents.ALL)

conf.logger.info(f"{conf.name} will now initialize into version {bot.version}.")
conf.logger.info("Extension loading complete.")


@bot.listen(hikari.ShardReadyEvent)
async def on_ready(event):
    bot.last_api_connection = localnow()
    conf.logger.info(f"API contact, {conf.name} is online.")

    bot.start_subroutines()
    bot.help = TopicContainer.build(bot)

    if conf.audio.lavalink_enabled:
        builder = (
            lavasnek_rs.LavalinkBuilder(bot.get_me().id, conf.token)
            .set_host(conf.audio.lavalink_addr)
            .set_password(conf.audio.lavalink_pass)
        )
        builder.set_start_gateway(False)
        lava_client = await builder.build(VoxEventHandler())
        bot.data.lavalink = lava_client

    if conf.dash.enabled:
        bot.dash = Dash(bot)
        loop = hikari.internal.aio.get_or_make_loop()
        loop.create_task(bot.dash.run())

    try:
        with open("reinit.json", "r") as file:
            data = json.load(file)
        await bot.rest.create_message(
            data["channel"],
            f"✔️ Reinitialization completed, current version is {bot.version}.",
        )
        conf.logger.debug(f"Reinitialization call at {data['time']} completed.")
        os.remove("reinit.json")
    except FileNotFoundError:
        pass


@bot.listen(hikari.GuildMessageCreateEvent)
async def on_guild_message_create(event):
    Member.process_event(bot, event)
    await Server.process_event(bot, event)

    vox = await Vox.getFromEvent(event, bot)
    await vox.processTTSEvent(event)

    await codeBlockCheck(bot, event)


@bot.listen(hikari.VoiceStateUpdateEvent)
async def voice_state_update(event):
    await bot.data.lavalink.raw_handle_event_voice_state_update(
        event.state.guild_id,
        event.state.user_id,
        event.state.session_id,
        event.state.channel_id
    )


@bot.listen(hikari.VoiceServerUpdateEvent)
async def voice_server_update(event):
    await bot.data.lavalink.raw_handle_event_voice_server_update(
        event.guild_id, event.endpoint, event.token
    )


@bot.listen(hikari.GuildReactionAddEvent)
async def guild_reaction_add(event):
    await Server.process_event(bot, event)


@bot.listen(hikari.events.ExceptionEvent)
async def on_error(event):
    conf.logger.debug(f"Command error event: {event.exception}.")
    if isinstance(event.exception, SlashCommandCheckFailure):
        return await event.exception.send_response()

    try:
        if isinstance(event.exception, lightbulb.errors.CommandInvocationError):
            raise event.exception.original
        raise event.exception
    except Exception:
        conf.logger.error(traceback.format_exc())
