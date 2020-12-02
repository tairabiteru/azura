"""
Core bot functions and initialization.

Everything comes together in this file to perform startup procedures,
validate settings, and initialize the bot upon startup.
"""

from libs.core.log import logprint, toilet_banner, toilet_version
from libs.core.conf import settings
from libs.core.help import Help
from libs.ext.utils import localnow, portIsOpen
from libs.dash.core import Dash
from libs.orm.revisioning import Revisioning

from aiohttp.web import AppRunner, TCPSite
from discord.ext import commands
import os
import pickle
import re
import traceback
import subprocess
import time
import wavelink


def revisionCalc():
    """Perform revisioning calulations."""
    rev = Revisioning.obtain()
    rev_logoutput = rev.calculate()
    return rev, rev_logoutput


class Azura:
    """Main bot class wraps discord.ext.commands.Bot."""

    def __init__(self):
        """Initialize bot instance and set up subroutines."""
        logprint("Initializing, please wait...")
        self.bot = self.initialize()
        self.settings = settings

        self.subroutines = []

    def run(self):
        """After initialzation, run the bot."""
        self.bot.run(settings['bot']['token'])

    def deconstruct(self):
        logprint("Terminating all subroutines...", type="warn")
        self.killSubroutines()
        logprint("Shutting down lavalink...", type="warn")
        self.killLavalink()
        logprint("All processes terminated. Bye!")

    def killSubroutines(self):
        """Cancel all subroutines. Called during exit."""
        logprint("Cancelling all subroutines...", type="warn")
        for subroutine in self.subroutines:
            if not subroutine.done():
                subroutine.cancel()

    def initLavalink(self):
        command = settings['wavelink']['jvmPath']
        path = settings['wavelink']['lavalinkPath']
        if settings['wavelink']['suppressLavalinkOutput']:
            with open(os.devnull, 'w') as out:
                self.lavalink_process = subprocess.Popen([command, "-jar", path], stdout=out, stderr=out)
        else:
            self.lavalink_process = subprocess.Popen([command, "-jar", path])
        while not portIsOpen(settings['wavelink']['host'], settings['wavelink']['port']):
            time.sleep(0.1)

    def killLavalink(self):
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

        toilet_banner(settings['bot']['name'])
        toilet_version(str(rev.current))
        print()
        rev_logoutput = rev_logoutput.split(":")
        if len(rev_logoutput) == 1:
            logprint(rev_logoutput[0])
        else:
            logprint(rev_logoutput[0] + ".", type="warn")
            logprint(rev_logoutput[1].lstrip(), type="warn")
        logprint("Loading cogs and libraries...")

        logprint("Initializing bot...")

        bot = commands.Bot(
            command_prefix=commands.when_mentioned_or(settings['bot']['commandPrefix']),
            description=settings['bot']['description'],
            help_command=Help()
        )

        bot.revision = rev
        bot.revised = False

        logprint("Version established as {version}".format(version=rev.current))

        self.initLavalink()

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
                logprint("Failed to load extension {extension}.".format(extension=extension), type='ERRR')
                traceback.print_exc()

        @bot.event
        async def on_ready():
            logprint("Logged in as {name}: #{id}.".format(name=bot.user.name, id=bot.user.id))
            try:
                channel = bot.get_channel(pickle.load(open("restart.init", "rb")))
                logprint("Reinitialization complete.")
                await channel.send("⚡ Reinitialization complete ⚡\nCurrent version is **{ver}**.".format(ver=bot.revision.current))
                os.remove("restart.init")
            except FileNotFoundError:
                logprint("Initialization complete.")

            # Initialize dashboard.
            if settings['dash']['enabled']:
                self.dash = Dash(bot)
                await self.dash.setup()
                self.dash_runner = AppRunner(self.dash.app)
                await self.dash_runner.setup()
                self.site = TCPSite(self.dash_runner, settings['dash']['host'], settings['dash']['port'])
                await self.site.start()

        @bot.event
        async def on_message(message):
            # Handle processing only when this regex returns a match.
            # This is to prevent things like -_- being intepreted as commands.
            if re.search("{}[a-z]+".format(settings['bot']['commandPrefix']), message.content):
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
                raise error

        return bot
