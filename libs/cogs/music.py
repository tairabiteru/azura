from libs.core.conf import settings
from libs.core.permissions import command
from libs.orm.member import Member
from libs.orm.playlist import PlaylistNotFoundError
from libs.ext.player import *

import asyncio
import itertools
import math
import random
import datetime
import os
import urllib.request
from bs4 import BeautifulSoup

import traceback

import discord
from async_timeout import timeout
from discord.ext import commands, tasks


LOWER_VOLUME = '\N{Speaker With One Sound Wave}'
RAISE_VOLUME = '\N{Speaker With Three Sound Waves}'
STOP = '\N{Black Square for Stop}'
PAUSE_RESUME = '\N{Black Right-Pointing Triangle With Double Vertical Bar}'
SKIP = '\N{Black Right-Pointing Double Triangle With Vertical Bar}'
LOOP = '🔁'


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    @staticmethod
    async def add_buttons(msg):
        await msg.add_reaction(LOWER_VOLUME)
        await msg.add_reaction(RAISE_VOLUME)
        await msg.add_reaction(STOP)
        await msg.add_reaction(PAUSE_RESUME)
        await msg.add_reaction(LOOP)
        await msg.add_reaction(SKIP)

    async def handle_button(self, reaction, user):
        if reaction.message.id == self.current.control_message.id:
            step = Member.obtain(user.id).volume_step
            if reaction.emoji == LOWER_VOLUME:
                volume = round(self.current.source.volume - step, 2)
                self.current.source.volume = volume if volume >= 0 and volume <= 100 else self.current.source.volume
            if reaction.emoji == RAISE_VOLUME:
                volume = round(self.current.source.volume + step, 2)
                self.current.source.volume = volume if volume >= 0 and volume <= 100 else self.current.source.volume
            if reaction.emoji == STOP:
                await self.stop()
                await self.current.source.channel.send("Stopped by " + user.name, delete_after=30)
                music = self.bot.get_cog("Music")
                del music.voice_states[reaction.message.channel.guild.id]
            if reaction.emoji == PAUSE_RESUME:
                if self._ctx.voice_state.voice.is_playing():
                    self._ctx.voice_state.voice.pause()
                elif self._ctx.voice_state.voice.is_paused():
                    self._ctx.voice_state.voice.resume()
            if reaction.emoji == SKIP:
                self.skip()
                await self.current.source.channel.send("Skipped by " + user.name, delete_after=30)
            if reaction.emoji == LOOP:
                self.loop = not self.loop
                msg = "Looping enabled by " + user.name if self.loop else "Looping disabled by " + user.name
                await self.current.source.channel.send(msg, delete_after=15)

    async def audio_player_task(self):
        try:
            await self.bot.wait_until_ready()
            while not self.bot.is_closed():
                self.next.clear()
                if not self.loop:
                    # Try to get the next song within 3 minutes.
                    # If no song will be added to the queue in time,
                    # the player will disconnect due to performance
                    # reasons.
                    try:
                        async with timeout(180):  # 3 minutes
                            self.current = await self.songs.get()
                    except asyncio.TimeoutError:
                        music = self.bot.get_cog("Music")
                        await self.stop() #self.bot.loop.create_task(self.stop())
                        del music.voice_states[self._ctx.guild.id]
                        return
                self.current.source.volume = self._volume
                if self.loop:
                    await self.current.reconstruct()
                self.voice.play(self.current.source, after=self.play_next_song)

                self.current.playback_message = await self.current.source.channel.send(embed=self.current.create_info_embed())

                self.current.source.start_time = datetime.datetime.now()
                self.current.source.status = "Now playing"

                self.current.control_message = await self.current.source.channel.send(embed=self.current.create_player_embed())
                await VoiceState.add_buttons(self.current.control_message)
                try:
                    while self.current.ctx.voice_client.is_playing() or self.current.ctx.voice_client.is_paused():
                        if self.current.ctx.voice_client.is_paused():
                            self.current.source.status = "Paused"
                            self.current.source.added_time += (datetime.datetime.now() - self.current.source.start_time).total_seconds()
                            await self.current.control_message.edit(embed=self.current.create_player_embed())
                            while self.current.ctx.voice_client.is_paused():
                                await asyncio.sleep(0.05)
                            self.current.source.start_time = datetime.datetime.now()
                        else:
                            self.current.source.status = "Now playing"
                            await self.current.control_message.edit(embed=self.current.create_player_embed())
                            await asyncio.sleep(1)
                except AttributeError:
                    pass
                await self.next.wait()
        except Exception as e:
            traceback.print_exc()


    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()
        if self.voice:
            await self.voice.disconnect()
            self.voice = None


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}
        self.ytdl_updated = True
        self.check_for_ytdl_update.start()

    @tasks.loop(minutes=30.0)
    async def check_for_ytdl_update(self):
        with urllib.request.urlopen("https://pypi.org/project/youtube_dl/") as response:
            html = BeautifulSoup(response.read(), "html.parser")
            latest_version = html.findAll("h1", {"class": "package-header__name"})[0].text.split("youtube_dl")[1].lstrip().rstrip()
            operating_version = os.popen("pip3 freeze | grep youtube-dl").read().split("youtube-dl==")[1].lstrip().rstrip()
            if latest_version != operating_version:
                if self.ytdl_updated:
                    self.ytdl_updated = False
                    print("Youtube DL has released a new version: " + latest_version)
                    print("Current operating version is " + operating_version)

    def cog_unload(self):
        self.check_for_ytdl_update.cancel()

    @check_for_ytdl_update.before_loop
    async def before_check_for_ytdl_update(self):
        await self.bot.wait_until_ready()

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    # async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
    #     await ctx.send('An error occurred: {}'.format(str(error)))

    @command(invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """Joins a voice channel."""
        await self.ensure_voice_state(ctx)
        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()


    @command(aliases=['vol'])
    async def volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player."""

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100')

        ctx.voice_state.volume = volume / 100
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @command(aliases=['current', 'playing', 'nowplaying', 'np'])
    async def now(self, ctx: commands.Context):
        """Displays the currently playing song."""
        ctx.voice_state.current.playback_message = await ctx.send(embed=ctx.voice_state.current.create_info_embed())
        ctx.voice_state.current.control_message = await ctx.send(embed=ctx.voice_state.current.create_player_embed())
        await VoiceState.add_buttons(ctx.voice_state.current.control_message)

    @command()
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""
        if ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @command()
    async def resume(self, ctx: commands.Context):
        """Resumes a currently paused song."""
        if ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @command()
    async def stop(self, ctx: commands.Context):
        """Stops playing song and clears the queue."""
        ctx.voice_state.songs.clear()
        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @command()
    async def skip(self, ctx: commands.Context):
        """Vote to skip a song. The requester can automatically skip.
        3 skip votes are needed for the song to be skipped.
        """
        if not ctx.voice_state.is_playing:
            return await ctx.send('Not playing any music right now...')

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 3:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                await ctx.send('Skip vote added, currently at **{}/3**'.format(total_votes))

        else:
            await ctx.send('You have already voted to skip this song.')

    @command()
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements.
        """

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='Viewing page {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @command()
    async def shuffle(self, ctx: commands.Context):
        """Shuffles the queue."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @command()
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index."""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @command()
    async def loop(self, ctx: commands.Context):
        """Loops the currently playing song.
        Invoke this command again to unloop the song.
        """

        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @command()
    async def play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """
        if not self.ytdl_updated:
            await ctx.send("YTDL has updated. Please inform Tyler.")
        if not ctx.voice_state.voice:
            await ctx.invoke(self.join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('An error occurred while processing this request: {}'.format(str(e)))
            else:
                song = YTDLSong(source, ctx, search, self.bot.loop)

                await ctx.voice_state.songs.put(song)
                await ctx.send('Enqueued {}'.format(str(source)))

    @command()
    async def enqueue(self, ctx: commands.Context, *, playlist):
        await ctx.invoke(self.join)
        member = Member.obtain(ctx.author.id)
        playlist, shuffle = parse_flags(playlist)
        try:
            await member.enqueue(self.bot, ctx, playlist, shuffle=shuffle)
        except PlaylistNotFoundError:
            await ctx.send("No playlist by that name exists.")

    @command(aliases=['xmas'])
    async def christmas(self, ctx: commands.Context):
        if datetime.datetime.now().month != 12:
            return await ctx.send("It's not even December.")
        await ctx.invoke(self.join)
        admin = Member.obtain(settings['bot']['ownerID'])
        await admin.enqueue(self.bot, ctx, "Christmas", shuffle=True)

    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('Bot is already in a voice channel.')

def setup(bot):
    """Set up cog."""
    bot.add_cog(Music(bot))
