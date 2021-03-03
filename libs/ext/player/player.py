from libs.core.conf import conf
from libs.ext.utils import ms_as_ts, progressBar, localnow
from libs.ext.player.queue import Queue, Repeat, EnqueueJob
from libs.ext.player.errors import AlreadyConnectedToChannel, NoVoiceChannel, QueueIsEmpty
from libs.orm.member import Member

import asyncio
import discord
import queue
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
        self.enqueueing = asyncio.Event()
        self.adv_all_clear = asyncio.Event()
        self.enq_all_clear = asyncio.Event()
        self.equalizer_name = "None"
        self.enqueueJobs = queue.Queue()
        self.current_job = None
        self.enqmsg = None

        self.adv_all_clear.set()
        self.enq_all_clear.set()



    async def connect(self, ctx, channel=None):
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if ctx.author.voice.channel is None:
            raise NoVoiceChannel
        else:
            channel =  ctx.author.voice.channel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.halt()
            self.queue.clear()
            self.enqueueJobs = queue.Queue()
            await self.destroy()
        except KeyError:
            pass

    async def halt(self):
        if self.current_job:
            self.current_job.cancel.set()
        self.enqueueJobs = queue.Queue()
        await self.stop()

    @property
    def current_repeat_mode(self):
        if self.queue.repeat_mode == Repeat.NONE:
            return "Off"
        elif self.queue.repeat_mode == Repeat.ONE:
            return "Current Song"
        elif self.queue.repeat_mode == Repeat.ALL:
            return "Current Queue"

    async def add_enqueue_job(self, ctx, wl, name, playlist, mode='FIFO'):
        job = EnqueueJob(ctx, wl, name, playlist, mode=mode)
        self.enqueueJobs.put(job)
        if not self.enqueueing.is_set():
            await self.enqueue_task()

    async def enqueue_task(self):
        while True:  # Should be replaced with bot.is_closed() or something
            if self.enqueueJobs.empty():
                break
            if not self.enqueueing.is_set():
                self.enqueueing.set()

            job = self.enqueueJobs.get()
            self.current_job = job
            await job.execute(self)

        self.current_job = None
        self.enqueueing.clear()

    async def choose_track(self, ctx, tracks):
        # Return first track if they have promptOnSearch turned off
        member = Member.obtain(ctx.author.id)
        if not member.settings.promptOnSearch:
            return tracks[0]

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
        self.enq_all_clear.clear()
        await self.adv_all_clear.wait()

        try:
            track = self.queue.get_next_track()
            if track is not None:
                if track.end != -1:
                    await self.play(track, start=track.start, end=track.end)
                else:
                    await self.play(track, start=track.start)
        except QueueIsEmpty:
            pass

        self.enq_all_clear.set()

    async def repeat_track(self):
        await self.play(self.queue.current_track)

    def completion_bar(self, length=conf.music.seekBarLength):
        total_time = self.queue.current_track.length
        progress = progressBar(self.position, total_time, length=length)
        time_left = ms_as_ts(total_time - self.position)
        total_time = ms_as_ts(total_time)
        return f"{time_left} {progress} {total_time}"

    def player_embed(self):
        status = "Paused" if self.is_paused else "Now Playing"
        embed = discord.Embed(title=f"Playback Status - {status}", colour=discord.Colour(0x14ff), description=f"`{self.completion_bar()}`")
        embed.add_field(name="Song Time Elapsed", value=ms_as_ts(self.position))
        embed.add_field(name="Song Time Left", value=ms_as_ts(self.queue.current_track.length - self.position))
        embed.add_field(name="Songs Played", value=len(self.queue.past_tracks))
        embed.add_field(name="Queue Time Elapsed", value=ms_as_ts(sum([track.length for track in self.queue.past_tracks]) + self.position))
        embed.add_field(name="Queue Time Left", value=ms_as_ts(sum([track.length for track in self.queue.next_tracks]) + (self.queue.current_track.length - self.position)))
        embed.add_field(name="Songs in Queue", value=len(self.queue.next_tracks))
        embed.add_field(name="Volume", value="{}%".format(self.volume))
        embed.add_field(name="Repeat", value=self.current_repeat_mode)
        embed.add_field(name="EQ", value=self.equalizer_name)
        return embed
