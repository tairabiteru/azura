from core.commands import (
    SlashCommand,
    SlashCommandGroup,
    SlashSubCommand,
    SlashSubGroup,
    load_slash_commands,
    unload_slash_commands,
)
from core.conf import conf
from ext.koe.exceptions import NoExistingSession

import aiohttp
from lightbulb.slash_commands import Option


JSON_HEADERS = {'Content-Type': 'application/json'}


class Connect(SlashCommand):
    description: str = f"Connect {conf.name} to the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        await ctx.bot.koe.fromCTX(ctx)
        await ctx.respond("Connected.")


class Disconnect(SlashCommand):
    description: str = f"Disconnect {conf.name} from the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.disconnect(ctx.bot.koe)
        except NoExistingSession as e:
            return await ctx.response(str(e))
        await ctx.respond("Disconnected.")


class Play(SlashCommand):
    description: str = "Play a song."
    enabled_guilds = [294260795465007105, 320759902240899073]

    song: str = Option("The name of the song or link to the song you want to play.")

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.play(ctx.bot.koe, ctx.author.id, ctx.options.song)
        except NoExistingSession as e:
            return await ctx.respond(str(e))


class Status(SlashCommand):
    description: str = f"Internal"
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        data = await ctx.bot.koe.companionVoiceViews()

        await ctx.respond(f"Responded with: `{data}`")


def load(bot):
    load_slash_commands(bot)


def unload(bot):
    unload_slash_commands(bot)
