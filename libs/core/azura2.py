"""
Core bot functions and initialization.

Everything comes together in this file to perform startup procedures,
validate settings, and initialize the bot upon startup.
"""
from libs.core.conf import conf2 as conf, confs
from libs.core.help import Help
from libs.ext.utils import portIsOpen, logHook
from libs.dash.core import Dash
from libs.orm.revisioning import Revisioning

from aiohttp.web import AppRunner, TCPSite
import discord
from discord.ext import commands
import os
import pickle
import re
import subprocess
import sys
import time
import traceback
import wavelink


sys.excepthook = logHook


def revisionCalc():
    """Perform revisioning calulations."""
    rev = Revisioning.obtain()
    rev_logoutput = rev.calculate()
    return rev, rev_logoutput


class Azura:
    """Main bot class wraps discord.ext.commands.Bot."""

    def __init__(self):
        """Initialize bot instance and set up subroutines."""
        self.conf = conf
        self.conf.logger.log("Initializing, please wait...")
        self.bot = self.initialize()

        self.subroutines = []

    def run(self):
        """After initialzation, run the bot."""
        self.bot.run(conf.token)

    def deconstruct(self):
        """Call before stopping the bot to cleanly exit."""
        self.bot.log("Terminating all subroutines...", type="warn")
        self.killSubroutines()
        self.bot.log("Shutting down lavalink...", type="warn")
        self.killLavalink()
        self.bot.log("All processes terminated. Bye!")

    def killSubroutines(self):
        """Cancel all subroutines. Called during exit."""
        self.bot.log("Cancelling all subroutines...", type="warn")
        for subroutine in self.subroutines:
            if not subroutine.done():
                subroutine.cancel()

    def initLavalink(self):
        """Initialize Lavalink node."""
        command = conf.wavelink.jvmPath
        path = conf.wavelink.lavalinkPath
        if not conf.wavelink.verbose:
            with open(os.devnull, 'w') as out:
                self.lavalink_process = subprocess.Popen([command, "-jar", path], stdout=out, stderr=out)
        else:
            self.lavalink_process = subprocess.Popen([command, "-jar", path])
        while not portIsOpen(conf.wavelink.host, conf.wavelink.port):
            time.sleep(0.1)

    def killLavalink(self):
        """Stop Lavalink node."""
        if conf.wavelink.run:
            self.lavalink_process.kill()

    def initialize(self):
        """
        Initialize bot.

        The bot first clears the console in anticipation of starting,
        then it performs revisioning calculations so that the banner text
        displayed on startup will be accurate. The bot then prints out the
        banner, and begins initializating the bot object itself. Extensions
        and cogs are then loaded, and then the bot defines all of the event
        listeners to be used.
        """
        os.system("clear")

        rev, rev_logoutput = revisionCalc()

        conf.logger.banner(conf.name)
        conf.logger.version(str(rev.current))
        print()
        rev_logoutput = rev_logoutput.split(":")
        if len(rev_logoutput) == 1:
            conf.logger.log(rev_logoutput[0])
        else:
            conf.logger.log(rev_logoutput[0] + ".", type="warn")
            conf.logger.log(rev_logoutput[1].lstrip(), type="warn")
        conf.logger.log("Loading cogs and libraries...")

        conf.logger.log("Initializing bot...")

        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True

        # See about taking '—' as a prefix too to correct iphones.
        bot = commands.Bot(
            command_prefix=commands.when_mentioned_or(conf.prefix),
            description=conf.description,
            help_command=Help(),
            intents=intents
        )

        bot.revision = rev
        bot.revised = False
        bot.logger = conf.logger
        bot.log = conf.logger.log

        bot.log(f"Version established as {rev.current}.")

        if conf.wavelink.run:
            self.initLavalink()
        bot.wavelink = wavelink.Client(bot=bot)

        extensions = [
            'libs.core.subroutines',
            'libs.cogs.admin',
            'libs.cogs.issues',
            'libs.cogs.music',
            'libs.cogs.playlisting'
        ]

        for extension in extensions:
            try:
                bot.load_extension(extension)
            except Exception:
                bot.log(f"Failed to load extension {extension}.", type='ERRR')
                traceback.print_exc()

        @bot.event
        async def on_ready():
            bot.log(f"Logged in as {bot.user.name}: #{bot.user.id}.")
            try:
                channel = bot.get_channel(pickle.load(open(f"{bot.user.id}_restart.init", "rb")))
                bot.log("Reinitialization complete.")
                await channel.send(f"⚡ Reinitialization complete ⚡\nCurrent version is **{bot.revision.current}**.")
                os.remove(f"{bot.user.id}_restart.init")
            except FileNotFoundError:
                bot.log("Initialization complete.")

            # Initialize dashboard.
            if conf.dash.enabled:
                self.dash = Dash(bot)
                await self.dash.setup()
                self.dash_runner = AppRunner(self.dash.app)
                await self.dash_runner.setup()
                self.site = TCPSite(self.dash_runner, conf.dash.host, conf.dash.port)
                await self.site.start()

        @bot.event
        async def on_message(message):
            # Handle processing only when this regex returns a match.
            # This is to prevent things like -_- being intepreted as commands.
            if any([message.content.startswith(c.prefix) for c in confs]) and not re.search("^{}[a-z]+".format(conf.prefix), message.content):
                return
            if re.search("^{}[a-z]+".format(conf.prefix), message.content):
                if message.author.voice:
                    if any([member.id in conf.exclusionaryIDs for member in message.author.voice.channel.members]):
                        return await message.channel.send("You already have a music bot connected. Please use that bot's prefix.")
                await bot.process_commands(message)

        @bot.event
        async def on_command_error(ctx, error):
            error = getattr(error, 'original', error)
            if isinstance(error, commands.CommandNotFound):
                await ctx.send("That is not a valid command.")
            if isinstance(error, commands.DisabledCommand):
                await ctx.send("That command is disabled. Go cry about it.")
            if isinstance(error, commands.CheckFailure):
                await ctx.send("Access is denied. You do not have sufficient permissions to run that command.")
            if isinstance(error, wavelink.errors.ZeroConnectedNodes):
                out = "I do not currently have a connection to lavalink.\n"
                out += "If I've recently been restarted, this is expected, and you should be more patient.\n"
                out += "Otherwise, please contact my maintainer."
                await ctx.send(out)
            else:
                try:
                    raise error
                except Exception:
                    bot.log(traceback.format_exc(), type="errr")

        @bot.event
        async def on_error(event, *args, **kwargs):
            bot.log(traceback.format_exc(), type="errr")

        return bot
