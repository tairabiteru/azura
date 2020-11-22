from libs.core.conf import settings
from libs.orm.member import Member
from libs.orm.songdata import GlobalSongData

import datetime
import asyncio
import youtube_dl
import discord
import functools
from discord.ext import commands

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ''


def parse_flags(cmdtext):
    args = cmdtext.split("--")
    playlist = args.pop(0).lstrip().rstrip()
    shuffle = False
    for arg in args:
        if "--" + arg == "--shuffle":
            shuffle = True

    return (playlist, shuffle)

def render_load_bar(progress, total, length=40):
    ratio = progress / total
    filled = "=" * int(length * ratio)
    unfilled = "-" * int(length - (length * ratio))
    return "`[" + filled + unfilled + "]`"


class VoiceError(Exception):
    pass


class YTDLError(Exception):
    pass


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '/home/taira/azura/%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0'
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -loglevel error',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = int(data.get('duration'))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = '{:,}'.format(int(data.get('view_count')))
        #self.likes = '{:,}'.format(int(data.get('like_count')))
        self.likes = "0"
        self.dislikes = "0" #'{:,}'.format(int(data.get('dislike_count')))
        self.stream_url = data.get('url')
        self.id = data.get('id')

        self.status = None
        self.start_time = 0
        self.added_time = 0

    def __str__(self):
        return '**{0.title}** by **{0.uploader}**'.format(self)

    @property
    def elapsed(self):
        if self.status != "Paused":
            return datetime.timedelta(seconds=(datetime.datetime.now() - self.start_time).total_seconds() + self.added_time)
        else:
            return datetime.timedelta(seconds=self.added_time)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        try:
            partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
            data = await loop.run_in_executor(None, partial)
        except Exception as e:
            print(search, e)

        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        try:
            partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
            processed_info = await loop.run_in_executor(None, partial)
        except Exception as e:
            print(webpage_url, e)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} days'.format(days))
        if hours > 0:
            duration.append('{} hours'.format(hours))
        if minutes > 0:
            duration.append('{} minutes'.format(minutes))
        if seconds > 0:
            duration.append('{} seconds'.format(seconds))

        return ', '.join(duration)

    @staticmethod
    def render_time(timedelta):
        rendered = ""
        if timedelta.total_seconds() >= 3600:
            rendered += str(int(timedelta.total_seconds() / 3600)) + ":"
            timedelta = timedelta.total_seconds() % 3600
        else:
            timedelta = timedelta.total_seconds()
        rendered += str(int(timedelta / 60)) + ":" if int(timedelta / 60) > 9 else "0" + str(int(timedelta / 60)) + ":"
        timedelta %= 60
        rendered += str(int(timedelta)) if int(timedelta) > 9 else "0" + str(int(timedelta))
        return rendered



class YTDLSong:
    __slots__ = ('source', 'requester', 'ctx', 'search', 'loop', 'playback_message', 'control_message')

    def __init__(self, source: YTDLSource, ctx, search, loop):
        self.source = source
        self.requester = source.requester

        self.ctx = ctx
        self.search = search
        self.loop = loop

        self.playback_message = None
        self.control_message = None

    async def reconstruct(self):
        self.source = await YTDLSource.create_source(self.ctx, self.search, loop=self.loop)

    def completion_bar(self, length=40):
        completion_ratio = self.source.elapsed.total_seconds() / self.source.duration
        bars_completed = "=" * int(length * completion_ratio)
        bars_left = "-" * (length - len(bars_completed))
        return YTDLSource.render_time(self.source.elapsed) + " [" + bars_completed + bars_left + "] " + YTDLSource.render_time(datetime.timedelta(seconds=self.source.duration - self.source.elapsed.total_seconds()))

    def create_info_embed(self):
        member = Member.obtain(self.requester.id)
        member.increment_playback(self.source.id, self.source.title)
        video_data = GlobalSongData.obtain(vid=self.source.id)
        embed = discord.Embed(title=self.source.title, colour=discord.Colour(0x14ff), url=self.source.url, description="Requested by: " + self.requester.name, timestamp=datetime.datetime.now())
        embed.set_image(url=self.source.thumbnail)
        embed.set_thumbnail(url="http://www.stickpng.com/assets/images/580b57fcd9996e24bc43c545.png")
        embed.set_author(name=self.ctx.bot.user.name, icon_url=self.ctx.bot.user.avatar_url)
        embed.set_footer(text=self.ctx.bot.user.name, icon_url=self.ctx.bot.user.avatar_url)
        embed.add_field(name="Playcount by Requester", value=str(video_data.plays_by(uid=self.requester.id)))
        embed.add_field(name="Playcount by Server", value=str(video_data.global_plays))
        embed.add_field(name="Duration", value=YTDLSource.render_time(datetime.timedelta(seconds=self.source.duration)))
        embed.add_field(name="Upload Date", value=self.source.upload_date)
        embed.add_field(name=":thumbsup: Likes", value=self.source.likes, inline=True)
        embed.add_field(name=":thumbsdown: Dislikes", value=self.source.dislikes, inline=True)
        embed.add_field(name="View Count", value=self.source.views, inline=True)
        embed.add_field(name="Video ID", value=self.source.id)
        return (embed)

    def create_player_embed(self):
        import traceback
        try:
            embed = discord.Embed(title="Playback Status - " + self.source.status, colour=discord.Colour(0x14ff), url="", description="`" + self.completion_bar() + "`")
            embed.add_field(name="Time Elapsed", value=YTDLSource.render_time(self.source.elapsed), inline=True)
            embed.add_field(name="Time Left", value=YTDLSource.render_time(datetime.timedelta(seconds=self.source.duration - self.source.elapsed.total_seconds())), inline=True)
            embed.add_field(name="Volume", value=str(round(self.source.volume * 100)) + "%", inline=True)
            return embed
        except Exception as e:
            print(traceback.print_exc())
