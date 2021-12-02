from core.commands import (
    SlashCommand,
    SlashCommandGroup,
    SlashSubCommand,
    load_slash_commands,
    unload_slash_commands,
)
from core.conf import conf
from ext.koe.exceptions import NoExistingSession
from ext.koe.queue import PositionError
from ext.koe.objects import Repeat
from ext.ctx import respond_with_timeout

import lavasnek_rs
from lightbulb.slash_commands import Option
import os
import typing


class Connect(SlashCommand):
    description: str = f"Connect {conf.name} to the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        await respond_with_timeout(ctx, "Acknowledged.", 5)
        session = await ctx.bot.koe.fromCTX(ctx)
        await session.connect()


class Disconnect(SlashCommand):
    description: str = f"Disconnect {conf.name} from the voice channel you're in."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            await respond_with_timeout(ctx, "Acknowledged.", 5)
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
            await respond_with_timeout(ctx, "Acknowledged.", 5)
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


class EnqueueFiles(SlashCommand):
    description: str = "Enqueue files"
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        files = list([os.path.join("/home/taira/music", file) for file in os.listdir("/home/taira/music")])
        try:
            await respond_with_timeout(ctx, "Acknowledged.", 5)
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.enqueueFilePlaylist(files)
        except NoExistingSession:
            session = await ctx.bot.koe.fromCTX(ctx)
            await session.connect()
            await session.enqueueFilePlaylist(files)
        except lavasnek_rs.NoSessionPresent:
            await session.delete()
            session = await ctx.bot.koe.fromCTX(ctx)
            await session.connect()
            await session.enqueueFilePlaylist(files)


class Pause(SlashCommand):
    description: str = "Pause or unpause playback."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            await respond_with_timeout(ctx, "Acknowledged.", 5)
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
            await respond_with_timeout(ctx, "Acknowledged.", 5)
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.volume(ctx.options.volume)
        except NoExistingSession as e:
            return await ctx.edit_response(str(e))


class Queue(SlashCommand):
    description: str = "Display the current queue."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            embed = await session.queue.getQueueEmbed()
            await respond_with_timeout(ctx, embed, 20)
        except NoExistingSession as e:
            await ctx.respond(str(e))


class RepeatMode(SlashCommand):
    description: str = "Change the repeat mode."
    enabled_guilds = [294260795465007105, 320759902240899073]
    name: str = "repeat"

    MODES = {
        'ONE': Repeat.ONE,
        'ALL': Repeat.ALL,
        'NONE': Repeat.NONE
    }

    mode: str = Option("The repeat mode to set.", choices=MODES.keys())

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.repeat(RepeatMode.MODES[ctx.options.mode])
            await respond_with_timeout(ctx, f"Set repeat mode to `Repeat {ctx.options.mode}`.", 5)
        except NoExistingSession:
            await respond_with_timeout(ctx, "I'm not connected to voice.", 5)


class Last(SlashCommand):
    description: str = "Move the queue back one song."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.move_by(-1)
            await ctx.respond("Moved back one song.")
        except PositionError:
            await ctx.respond("You've reached the beginning of the queue.")


class Skip(SlashCommand):
    description: str = "Move the queue forward one song."
    enabled_guilds = [294260795465007105, 320759902240899073]

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.move_by(1, stop=True)
            await ctx.respond("Moved forward one song.")
        except PositionError:
            await ctx.respond("You've reached the end of the queue.")


class Move(SlashCommandGroup):
    description: str = "Move the queue position."
    enabled_guilds = [294260795465007105, 320759902240899073]


@Move.subcommand()
class To(SlashSubCommand):
    description: str = "Move the queue to a specific position."

    position: int = Option("The position to move to. A number between 1 and the length of the queue.")

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.move_to(ctx.options.position-1)
            await ctx.respond(f"Moved to queue position #`{ctx.options.position}`.")
        except PositionError as e:
            await ctx.respond(str(e))


@Move.subcommand()
class By(SlashSubCommand):
    description: str = "Move the queue by a number of positions."

    positions: int = Option("The number of positions to move. Can be negative to move backwards.")

    async def callback(self, ctx):
        try:
            session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
            await session.move_by(ctx.options.positions)
            plural = "position" if ctx.options.positions in [1, -1] else "positions"
            await ctx.respond(f"Moved the queue by `{ctx.options.positions}` {plural}.")
        except PositionError as e:
            await ctx.respond(str(e))


class Enqueue(SlashCommand):
    description: str = "Enqueue a playlist."
    enabled_guilds = [294260795465007105, 320759902240899073]

    MODES = [
        'AT BACK',
        'AT FRONT',
        'RANDOM',
        'INTERLACE'
    ]

    playlist: str = Option("The name of the playlist to enqueue.")
    shuffle: typing.Optional[bool] = Option("Whether or not the playlist should be shuffled before enqueueing.")
    mode: typing.Optional[str] = Option("The enqueueing mode to use. Defaults to AT BACK.", choices=MODES, default="AT BACK")

    async def callback(self, ctx):
        session = await ctx.bot.koe.fromCTX(ctx, must_exist=True)
        await ctx.bot.lavalink.get_guild_node(session.gid)


def load(bot):
    load_slash_commands(bot)


def unload(bot):
    unload_slash_commands(bot)
