from libs.core.conf import settings
from libs.ext.utils import ms_as_ts, url_is_valid, progressBar, localnow
from libs.ext.player.queue import Queue, Repeat
from libs.ext.player.track import Track
from libs.ext.player.errors import AlreadyConnectedToChannel, NoVoiceChannel, NoTracksFound, QueueIsEmpty

import asyncio
import random
import discord
import wavelink


OPTSR = {
    "1️⃣": 0,
    "2️⃣": 1,
    "3️⃣": 2,
    "4️⃣": 3,
    "5️⃣": 4,
}

OPTSM = {
    '1': 0,
    '2': 1,
    '3': 2,
    '4': 3,
    '5': 4,
}


class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()
        self.enqueueing = False
        self.stop_signal = False


    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel := getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            self.queue.clear()
            await self.destroy()
        except KeyError:
            pass

    @property
    def current_repeat_mode(self):
        if self.queue.repeat_mode == Repeat.NONE:
            return "Off"
        elif self.queue.repeat_mode == Repeat.ONE:
            return "Current Song"
        elif self.queue.repeat_mode == Repeat.ALL:
            return "Current Queue"

    async def add_playlist(self, ctx, wl, playlist):
        enqueued = []
        failures = []
        length = settings['wavelink']['compBarLength']
        progress = progressBar(0, len(playlist), length=length)
        progressMsg = await ctx.send(f"Enqueueing {len(playlist)} song(s)\n`0 {progress} {len(playlist)}`")
        self.enqueueing = True
        for i, entry in enumerate(playlist):
            if self.stop_signal:
                self.queue.clear()
                break

            if not url_is_valid(entry.generator):
                query = f"ytsearch:{entry.generator}"
            else:
                query = entry.generator
            tracks = await wl.get_tracks(query)
            if not tracks:
                failures.append(entry)
                continue

            track = Track(tracks[0], ctx=ctx, requester=ctx.author, start=entry.start, end=entry.end)
            self.queue.add(track)
            enqueued.append(track)

            progress = progressBar(i+1, len(playlist), length=length)
            await progressMsg.edit(content=f"Enqueueing {len(playlist)} song(s)\n`{i+1} {progress} {len(playlist)}`")
            await asyncio.sleep(settings['wavelink']['enqueueingShotDelay'])
            if not self.is_playing and not self.queue.empty:
                await self.start_playback()

        # Should be replaced with some kind of exception.
        # Ex: raise EnqueueingStopped
        self.enqueueing = False
        self.stop_signal = False
        return (enqueued, failures)

    async def add_tracks(self, ctx, tracks):
        if not tracks:
            raise NoTracksFound

        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks)
        elif len(tracks) == 1:
            track = Track(tracks[0], ctx=ctx, requester=ctx.author)
            self.queue.add(track)
            await ctx.send(f"Added {tracks[0].title} to the queue.")
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None:
                track = Track(track, ctx=ctx, requester=ctx.author)
                self.queue.add(track)
                await ctx.send(f"Added {track.title} to the queue.")

        if not self.is_playing and not self.queue.empty:
            await self.start_playback()

    async def choose_track(self, ctx, tracks):
        def r_check(r, u):
            return (r.emoji in OPTSR.keys() and u == ctx.author and r.message.id == msg.id)

        def m_check(m):
            return (m.content in OPTSM.keys() and m.author == ctx.author)

        embed = discord.Embed(
            title="Choose a song",
            description=(
                "\n".join(
                    f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
                    for i, t in enumerate(tracks[:5])
                )
            ),
            colour=ctx.author.colour,
            timestamp=localnow()
        )
        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Invoked by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTSR.keys())[:min(len(tracks), len(OPTSR))]:
            await msg.add_reaction(emoji)

        try:
            tasks = [
                self.bot.wait_for("reaction_add", timeout=60.0, check=r_check),
                self.bot.wait_for("message", timeout=60.0, check=m_check)
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            is_reaction = True
            try:
                for task in done:
                    reaction, _ = task.result()
            except TypeError:
                for task in done:
                    message = task.result()
                    is_reaction = False

            for task in pending:
                task.cancel()
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete()
        else:
            await msg.delete()
            if is_reaction:
                return tracks[OPTSR[reaction.emoji]]
            else:
                await message.delete()
                await ctx.message.delete()
                return tracks[OPTSM[message.content]]

    async def start_playback(self):
        track = self.queue.current_track
        if track.end != -1:
            await self.play(track, start=track.start, end=track.end)
        else:
            await self.play(track, start=track.start)

    async def advance(self):
        try:
            if (track := self.queue.get_next_track()) is not None:
                if track.end != -1:
                    await self.play(track, start=track.start, end=track.end)
                else:
                    await self.play(track, start=track.start)
        except QueueIsEmpty:
            pass

    async def repeat_track(self):
        await self.play(self.queue.current_track)

    def completion_bar(self, length=settings['wavelink']['compBarLength']):
        total_time = self.queue.current_track.length
        progress = progressBar(self.position, total_time, length=length)
        time_left = ms_as_ts(total_time - self.position)
        total_time = ms_as_ts(total_time)
        return f"{time_left} {progress} {total_time}"

    def player_embed(self):
        status = "Paused" if self.is_paused else "Now Playing"
        embed = discord.Embed(title=f"Playback Status - {status}", colour=discord.Colour(0x14ff), description="`{}`".format(self.completion_bar()))
        embed.add_field(name="Time Elapsed", value=ms_as_ts(self.position))
        embed.add_field(name="Time Left", value=ms_as_ts(self.queue.current_track.length - self.position))
        embed.add_field(name="Volume", value="{}%".format(self.volume))
        embed.add_field(name="Repeat", value=self.current_repeat_mode)
        return embed
