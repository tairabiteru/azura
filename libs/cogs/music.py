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
        self._volume = 0.25
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
                        await self.stop()
                        del music.voice_states[self._ctx.guild.id]
                        return
                member = Member.obtain(self._ctx.author.id)
                self.volume = member.last_volume
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
                        self.current.source.volume = self._volume
                        if self.current.ctx.voice_client.is_paused():
                            self.current.source.status = "Paused"
                            self.current.source.added_time += (datetime.datetime.now() - self.current.source.start_time).total_seconds()
                            await self.current.control_message.edit(embed=self.current.create_player_embed())
                            while self.current.ctx.voice_client.is_paused():
                                self.current.source.volume = self._volume
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
            if self.is_playing:
                self.voice.stop()
            self.voice.play(discord.FFmpegPCMAudio(os.path.join(settings['bot']['assetDirectory'], "disconnecting.mp3")))
            while self.current.ctx.voice_client.is_playing():
                await asyncio.sleep(0.05)
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

    @command(aliases=['con', 'connect'], invoke_without_subcommand=True)
    async def join(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Connects the bot to the channel the command executor is in. This does
        not need to be executed before playing music, but the command exists
        regardless for troubleshooting purposes.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        await self.ensure_voice_state(ctx)
        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()


    @command(aliases=['vol'])
    async def volume(self, ctx: commands.Context, *, volume: int):
        """
        Syntax: `{pre}{command_name} <volume>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Set the playback volume to the specified percentage.
        Volume settings persist and do not reset, so you set the volume to, say,
        10%, and then a few days later play a song, the volume will be 10% still.
        This setting is specific to each user. The maximum allowed volume is 100%.
        This can only be used if something is actively being played.

        __**Arguments**__
        `<volume>` - The volume level to set to. Must be a whole integer between
        0 and 100.

        __**Example Usage**__
        `{pre}{command_name} 50`
        `{pre}{command_name} 10`
        """
        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        if 0 > volume > 100:
            return await ctx.send('Volume must be between 0 and 100')

        member = Member.obtain(ctx.author.id)
        ctx.voice_state.volume = volume / 100.0
        member.last_volume = volume / 100.0
        member.save()
        await ctx.send('Volume of the player set to {}%'.format(volume))

    @command(aliases=['current', 'playing', 'nowplaying', 'np'])
    async def now(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Show the now playing message. This simply re-displays the message sent
        when the bot first begins playing music. It's useful if the message
        has gotten lost after other commands have been run.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        ctx.voice_state.current.playback_message = await ctx.send(embed=ctx.voice_state.current.create_info_embed())
        ctx.voice_state.current.control_message = await ctx.send(embed=ctx.voice_state.current.create_player_embed())
        await VoiceState.add_buttons(ctx.voice_state.current.control_message)

    @command()
    async def pause(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Pauses playback. Can be unpaused with `{pre}resume`.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @command(aliases=['unpause'])
    async def resume(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Resumes a song that has been paused.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @command(aliases=['dc', 'disconnect'])
    async def stop(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Stops playing the current song, clears the queue, and disconnects from chat.
        This will also halt any current enqueuing process. (I.E. if you have songs
        that are being enqueued, this will stop that.)

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        ctx.voice_state.songs.clear()
        if ctx.voice_state.is_playing:
            await ctx.voice_state.stop()
            await ctx.message.add_reaction('⏹')

    @command()
    async def skip(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Skips the current song and moves to the next song in the queue. If no
        songs are left in the queue, playback simply stops altogether. Only
        the person who requested the song, or the bot owner may skip songs.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if not ctx.voice_state.is_playing:
            return await ctx.send('Not playing any music right now...')

        voter = ctx.message.author
        if ctx.author.id == ctx.voice_state.current.requester.id or ctx.author.id == settings['bot']['ownerID']:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()
        else:
            return await ctx.send("To skip a song, you must either be the owner, or the person who requested it.")

    @command()
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """
        Syntax: `{pre}{command_name} [page]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Displays the current song queue, ten songs at a time. If more than 10
        songs are enqueued, `[page]` can be specified to see past the first
        page of songs. If no `[page]` number is specified, it defaults to 1.

        __**Arguments**__
        `[page]` - The page number of the queue to see. If not specified, it
        defaults to page 1.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} 2`
        """
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('The queue is currently empty.')

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
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Shuffles the current queue. Obviously, there must be queue to shuffle,
        so there needs to be things in the queue already.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('The queue is currently empty.')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @command(aliases=['rm'], grant_level="explicit")
    async def remove(self, ctx: commands.Context, index: int):
        """
        Syntax: `{pre}{command_name} <index>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Removes a song in the queue at the specified `<index>`.

        __**Arguments**__
        `<index>` - The index number of the song to be removed.

        __**Example Usage**__
        `{pre}{command_name} 1`
        `{pre}{command_name} 7`
        """
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @command(aliases=['repeat'])
    async def loop(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Loops the current song. When executed, the current song will be played
        over and over until either stopped, or until this command is run again.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if not ctx.voice_state.is_playing:
            return await ctx.send('Nothing being played at the moment.')

        # Inverse boolean value to loop and unloop.
        ctx.voice_state.loop = not ctx.voice_state.loop
        if ctx.voice_state.loop:
            return await ctx.send("Looping is enabled.")
        else:
            return await ctx.send("Looping is disabled.")

    @command()
    async def play(self, ctx: commands.Context, *, search: str):
        """
        Syntax: `{pre}{command_name} <generator>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Plays the specified song. If there are songs in the queue, the specified
        song will be enqueued at the end of the queue, and played once the
        other songs have finished playing.

        This command automatically searches various sites if a URL is not
        specified. A list of these sites can be found here:
        https://rg3.github.io/youtube-dl/supportedsites.html
        In general, anything on Youtube should work.

        __**Arguments**__
        `<generator>` - The search term or URL that corresponds to the song.
        This can be either the name of the song, or the URL.

        __**Example Usage**__
        `{pre}{command_name} https://www.youtube.com/watch?v=dQw4w9WgXcQ`
        `{pre}{command_name} Smash Mouth - Allstar`
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
        """
        Syntax: `{pre}{command_name} <playlist> [--shuffle]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues the specified playlist. It will by default enqueue it in the
        order in which it appears in the playlist itself. `--shuffle` can also
        be specified at the end to randomize the order.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued.
        `[--shuffle]` - If specified, the playlist will be enqueued in random order.

        __**Example Usage**__
        `{pre}{command_name} Lo-Fi`
        `{pre}{command_name} Electronic --shuffle`
        """
        await ctx.invoke(self.join)
        member = Member.obtain(ctx.author.id)
        playlist, shuffle = parse_flags(playlist)
        try:
            playlist = member.entries_in_playlist(playlist)
        except PlaylistNotFoundError:
            return await ctx.send("No playlist named `{}` exists".format(playlist))
        if shuffle:
            random.shuffle(playlist)
        songs = []
        song_number = 1
        enqueueing_message = await ctx.send("Enqueuing song 1 of {}\n{}...\n{}".format(len(playlist), playlist[0].name, render_load_bar(song_number, len(playlist))))
        for entry in playlist:
            if not ctx.voice_client:
                await enqueueing_message.edit(content="Enqueuing cancelled due to disconnected voice state.")
                break
            try:
                source = await YTDLSource.create_source(ctx, entry.generator, loop=self.bot.loop)
                song = YTDLSong(source, ctx, entry.generator, self.bot.loop)
                songs.append(song)
                await ctx.voice_state.songs.put(song)
                await enqueueing_message.edit(content="Enqueuing song {} of {}\n{}...\n{}".format(song_number, len(playlist), playlist[song_number-1].name, render_load_bar(song_number, len(playlist))))
                song_number += 1
            except YTDLError as e:
                await ctx.send("An error occurred while processing this request: {}".format(str(e)))

        if song_number >= len(playlist):
            msg = "Enqueued {} songs." if len(songs) != 1 else "Enqueued 1 song."
            await enqueueing_message.edit(content=msg)

    @command(aliases=['xmas'])
    async def christmas(self, ctx: commands.Context):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a special Christmas playlist. (If you want songs added to it,
        contact Taira.) This command can only be successfully run during the
        month of December.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
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
