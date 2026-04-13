import datetime
import random

import koe
import lightbulb

from ...core.conf import Config
from ...lib.hooks import (
    SessionError,
    require_existing_session,
    require_no_session,
    require_user_in_voice,
)
from ...lib.injection.ctx import Context
from ...mvc.discord.models import User
from ...mvc.music.models import Playlist, Song, Stream

conf = Config.load()
music = lightbulb.Loader()


@music.command
class Connect(
    lightbulb.SlashCommand,
    name="connect",
    description=f"Connect {conf.name} to your voice channel.",
    hooks=[require_user_in_voice, require_no_session],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        assert ctx.voice_id is not None
        await session.connect(
            ctx.guild_id, ctx.voice_id, channel_id=ctx.channel_id, user_id=ctx.user.id
        )
        await ctx.respond("Connected.")


@music.command
class Disconnect(
    lightbulb.SlashCommand,
    name="disconnect",
    description=f"Disconnect {conf.name} from the current voice channel.",
    hooks=[require_existing_session, require_user_in_voice],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        await session.disconnect(user_id=ctx.user.id)
        await ctx.respond("Disconnected.")


@music.command
class Play(
    lightbulb.SlashCommand,
    name="play",
    description="Play a song.",
    hooks=[require_user_in_voice],
):
    name = lightbulb.string("name", "The name of the file to play.")

    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        songs = await Song.search(self.name)
        if any(songs):
            if session._connected is False and ctx.voice_id is not None:
                await session.connect(
                    ctx.guild_id,
                    ctx.voice_id,
                    channel_id=ctx.channel_id,
                    user_id=ctx.user.id,
                )

            track = await ctx.bot.koe.load_tracks(songs[0][1].file.path)
            assert isinstance(track, koe.Track)
            s = await Song.objects.aget(
                file__contains=track.info.identifier.split("/")[-1]
            )
            await session.enqueue(track, user_id=ctx.user.id)
            await ctx.respond(f"Playing `{songs[0][1].name}`")
        else:
            await ctx.respond(f"No songs found by the search term `{self.name}`.")


@music.command
class StreamCmd(
    lightbulb.SlashCommand,
    name="stream",
    description="Stream.",
    hooks=[require_user_in_voice],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session, user: User):
        try:
            stream = await Stream.objects.aget(author=user)
        except Stream.DoesNotExist:
            return await ctx.respond("No stream found for this user.")

        track = await ctx.bot.koe.load_tracks(stream.uri)
        await session.play(track)
        await ctx.respond(f"Connected to `{stream.name}`")


@music.command
class Stop(
    lightbulb.SlashCommand,
    name="stop",
    description="Stop playback.",
    hooks=[require_user_in_voice, require_existing_session],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        await session.stop(user_id=ctx.user.id)
        await ctx.respond("Playback halted.")


@music.command
class Volume(lightbulb.SlashCommand, name="volume", description="Set volume."):
    level = lightbulb.string("level", "The new volume level. Ex: 50, +5, -10, etc...")

    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        if self.level.startswith("+") or self.level.startswith("-"):
            await session.incr_volume(int(self.level), user_id=ctx.user.id)
        else:
            await session.set_volume(int(self.level), user_id=ctx.user.id)

        await ctx.respond(f"Set volume to {session._volume}%.")


@music.command
class Skip(
    lightbulb.SlashCommand,
    name="skip",
    description="Skip to a track, or by a number.",
    hooks=[require_user_in_voice, require_existing_session],
):
    skip = lightbulb.string(
        "skip", "The number to skip to or by, ex: 3, +2, -1, etc..."
    )

    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        try:
            if self.skip.startswith("+") or self.skip.startswith("-"):
                num = int(self.skip)
                await session.skip(by=num, user_id=ctx.user.id)
            else:
                num = int(self.skip)
                await session.skip(to=num, user_id=ctx.user.id)
            await ctx.respond(f"Skipped `{self.skip}`")
        except koe.errors.InvalidPosition as e:
            await ctx.respond(str(e))


@music.command
class Pause(lightbulb.SlashCommand, name="pause", description="Pause playback."):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        success = await session.set_pause(True, user_id=ctx.user.id)
        if not success:
            await ctx.respond("I'm already paused.")
            return

        await ctx.respond("Playback paused.")


@music.command
class Resume(lightbulb.SlashCommand, name="resume", description="Resume playback."):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        success = await session.set_pause(False, user_id=ctx.user.id)
        if not success:
            await ctx.respond("Playback is not paused.")
            return

        await ctx.respond("Playback resumed.")


@music.error_handler
async def handle_error(
    error: lightbulb.exceptions.ExecutionPipelineFailedException,
) -> bool:
    if isinstance(error.causes[0], SessionError):
        se = error.causes[0]
        await error.context.respond(se.message)
        return True

    return False


@music.command
class Christmas(
    lightbulb.SlashCommand,
    name="christmas",
    description="Enqueues a Christmas playlist.",
    hooks=[require_user_in_voice, require_existing_session],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session, user: User):
        now = user.localnow
        thanksgiving = now
        thanksgiving = thanksgiving.replace(hour=0, minute=0, second=0, microsecond=0)
        thanksgiving = thanksgiving.replace(month=11, day=1)
        while thanksgiving.weekday() != 3:
            thanksgiving += datetime.timedelta(days=1)

        thanksgiving += datetime.timedelta(days=21)
        if now < thanksgiving:
            await ctx.respond("Oh, come on. It's not even after thanksgiving yet.")
            return

        playlist = await Playlist.objects.aget(id=1)
        songs = []
        async for song in playlist.songs.all():
            songs.append(song)

        random.shuffle(songs)
        for song in songs:
            track = await ctx.bot.koe.load_tracks(song.file.path)
            await session.enqueue(track, user_id=ctx.user.id)

        await ctx.respond("Enqueued Christmas playlist.")


@music.command
class History(
    lightbulb.SlashCommand,
    name="history",
    description="See the current session's action history.",
    hooks=[require_user_in_voice, require_existing_session],
):
    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session):
        history = await session.get_history()
        msg = "**These are the last 20 actions performed in this session:**\n```"

        for record in history[-20:]:
            actor = record.get_actor(ctx.bot)
            assert actor is not None

            msg += f"[{record.time}] {record.action} by {actor.display_name}\n"
        msg += "```"
        await ctx.respond(msg)


@music.command
class Enqueue(
    lightbulb.SlashCommand,
    name="enqueue",
    description="Enqueue a playlist.",
    hooks=[require_user_in_voice],
):
    name = lightbulb.string("name", "The name of the playlist.")

    @lightbulb.invoke
    async def invoke(self, ctx: Context, session: koe.Session, user: User):
        try:
            playlist = await Playlist.objects.aget(owner=user, name=self.name)
        except Playlist.DoesNotExist:
            await ctx.respond(f"You don't have a playlist named `{self.name}`.")
            return

        async for song in playlist.songs.all():
            track = await session.koe.load_tracks(song.file.path)
            await session.enqueue(track, user_id=ctx.user.id)

        await ctx.respond(f"Enqueued your playlist, `{playlist.name}`.")
