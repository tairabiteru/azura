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
import lavasnek_rs
from lightbulb.slash_commands import Option
import typing


class Connect(SlashCommand):
    description: str = f"Connect {conf.name} to the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        await ctx.respond("Acknowledged.")
        session = await ctx.bot.koe.fromCTX(ctx)
        await session.connect()


class Disconnect(SlashCommand):
    description: str = f"Disconnect {conf.name} from the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            await ctx.respond("Acknowledged.")
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.disconnect()
        except NoExistingSession as e:
            return await ctx.edit_response(str(e))


class Play(SlashCommand):
    description: str = "Play a song."
    enabled_guilds = [294260795465007105, 320759902240899073]

    song: str = Option("The name of the song or link to the song you want to play.")

    async def callback(self, ctx):
        try:
            await ctx.respond("Acknowledged.")
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.play(ctx.author.id, ctx.options.song)
        except NoExistingSession:
            session = await ctx.bot.koe.fromCTX(ctx)
            await session.connect()
            await session.play(ctx.author.id, ctx.options.song)
        except lavasnek_rs.NoSessionPresent:
            await session.delete()
            session = await ctx.bot.koe.fromCTX(ctx)
            await session.connect()
            await session.play(ctx.author.id, ctx.options.song)


class Pause(SlashCommand):
    description: str = "Pause or unpause playback."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            await ctx.respond("Acknowledged.")
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.pause()
        except NoExistingSession as e:
            return await ctx.edit_response(str(e))


class Volume(SlashCommand):
    description: str = "Set the player volume."
    enabled_guilds = [294260795465007105, 320759902240899073]

    volume: int = Option("The volume level in percent. Must be between 0 and 1,000.")

    async def callback(self, ctx):
        try:
            await ctx.respond("Acknowledged.")
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.volume(ctx.options.volume)
        except NoExistingSession as e:
            return await ctx.edit_response(str(e))


class Enqueue(SlashCommand):
    description: str = "Enqueue a playlist."
    enabled_guilds = [294260795465007105, 320759902240899073]

    MODES = [
        'FIFO',
        'LIFO',
        'RANDOM',
        'INTERLACE'
    ]

    playlist: str = Option("The name of the playlist to enqueue.")
    shuffle: typing.Optional[bool] = Option("Whether or not the playlist should be shuffled before enqueueing.")
    mode: typing.Optional[str] = Option("The enqueueing mode to use. Defaults to FIFO.", choices=MODES)

    async def callback(self, ctx):
        pass


def load(bot):
    load_slash_commands(bot)


def unload(bot):
    unload_slash_commands(bot)
