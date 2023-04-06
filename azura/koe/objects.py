import asyncio
import datetime
import hikari
import miru

from ext.utils import strfdelta
from koe.enums import RepeatMode
import orm.models as models


def build_timeline(position, length):
    LENGTH = 40

    if position == -1:
        position = length

    percent = position / length
    complete = "━" * int(percent * LENGTH)
    left = "╸" * int(LENGTH - (percent * LENGTH))
    timeline = f"[{complete}➤{left}]"

    position = strfdelta(datetime.timedelta(seconds=position/1000), '{%H}:{%M}:{%S}')
    length = strfdelta(datetime.timedelta(seconds=length/1000), '{%H}:{%M}:{%S}')
    return f"{position} `{timeline}` {length}"


class NowPlayingEmbed(hikari.Embed):
    def __init__(self, requester, title, position, length, volume, state, repeat, queue, url):
        self.requester = requester
        self.position = position
        self.length = length
        self.volume = volume
        self.state = state
        self.repeat = repeat
        self.queue = queue

        super().__init__(title=title, url=url)
        self.update()
    
    @property
    def thumbnail_image(self):
        if self.url:
            if self.url.startswith("http://") or self.url.startswith("https://"):
                if "youtube" in self.url:
                    vid = self.url.split("=")[-1]
                    if len(vid) != 11:
                        return None
                    return f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"

    def update(self):
        self._fields = None
        self.description = self.get_timeline(self.position, self.length)
        self.add_field(name="Requester", value=self.requester, inline=True)
        self.add_field(name="Volume", value=f"{self.volume}%", inline=True)
        self.add_field(name="State", value=self.state, inline=True)
        self.add_field(name="Repeat", value=self.repeat, inline=True)
        self.add_field(name="Queue", value=self.queue)

        if self.thumbnail_image:
            self.set_thumbnail(self.thumbnail_image)

    def get_timeline(self, position, length):
        return build_timeline(position, length)

    @classmethod
    async def from_session(cls, session, volume, state, position=0, trackqueue=None):
        node = await session.lavalink.get_guild_node(session.guild_id)
        trackqueue = node.now_playing if trackqueue is None else trackqueue
    
        try:
            requester = session.bot.cache.get_user(trackqueue.requester)
            requester = requester.username
        except AttributeError:
            requester = "Unknown"

        title = trackqueue.track.info.title
        url = trackqueue.track.info.uri if "http" in trackqueue.track.info.uri else None
        length = trackqueue.track.info.length
        queue = await session._queue.get_contents()
        return cls(requester, title, position, length, volume, state.value, session._repeat_mode.value, queue, url)


class PlaybackControls(miru.View):
    def __init__(self, session, *args, **kwargs):
        self.session = session
        kwargs['timeout'] = None
        super().__init__(*args, **kwargs)
    
    # Method should only be called inside of session lock!
    async def _update(self):
        at_start = await self.session._queue.is_at_start()
        at_end = await self.session._queue.is_at_end()
        state = self.session._state.value

        self.skip_back.disabled = at_start
        self.toggle_pause.disabled = True if state not in ["Playing", "Paused"] else False
        self.skip_next.disabled = at_end

    @miru.button(label="⏪", style=hikari.ButtonStyle.SUCCESS)
    async def skip_back(self, button, ctx):
        await self.session._skip(by=-1)

    @miru.button(label="🔁", style=hikari.ButtonStyle.SUCCESS)
    async def toggle_repeat(self, button, ctx):
        mode = await self.session._get_repeat_mode()
        if mode is RepeatMode.NONE:
            await self.session.set_repeat_mode(RepeatMode.ONE)
        elif mode is RepeatMode.ONE:
            await self.session.set_repeat_mode(RepeatMode.ALL)
        elif mode is RepeatMode.ALL:
            await self.session.set_repeat_mode(RepeatMode.NONE)
    
    @miru.button(label="⏹️", style=hikari.ButtonStyle.DANGER)
    async def stop_button(self, button, ctx):
        await self.session.bot.koe.destroy_session(self.session.voice_id, must_exist=True, send_termination=True)

    @miru.button(label="⏯️", style=hikari.ButtonStyle.SUCCESS)
    async def toggle_pause(self, button, ctx):
        await self.session.pause(internal=True)

    @miru.button(label="⏩", style=hikari.ButtonStyle.SUCCESS)
    async def skip_next(self, button, ctx):
        await self.session._skip(by=1)

    @miru.button(label="🔉", style=hikari.ButtonStyle.SUCCESS)
    async def volume_down(self, button, ctx):
        user = await models.User.get_or_create(ctx.user)
        await self.session.set_volume(user, increment=-(user.volume_step), internal=True)

    @miru.button(label="🔊", style=hikari.ButtonStyle.SUCCESS)
    async def volume_up(self, button, ctx):
        user = await models.User.get_or_create(ctx.user)
        await self.session.set_volume(user, increment=user.volume_step, internal=True)


class PlaylistSelect(miru.Select):
    def __init__(self, playlists, *args, **kwargs):
        self.playlists = playlists

        options = []
        for playlist in self.playlists:
            options.append(miru.SelectOption(playlist.name))
        kwargs['options'] = options
        kwargs['placeholder'] = "Select a playlist..."
        super().__init__(*args, **kwargs)

    async def callback(self, ctx):
        playlist = self.values[0]
        self.view.selection = playlist


class ShuffleSelect(miru.Select):
    def __init__(self, *args, **kwargs):
        kwargs['options'] = [
            miru.SelectOption("Shuffle: Off", is_default=True),
            miru.SelectOption("Shuffle: On")
        ]
        kwargs['placeholder'] = "Shuffle: Off"
        super().__init__(*args, **kwargs)
    
    async def callback(self, ctx):
        self.view.shuffle = True if self.values[0].endswith("On") else False


class ModeSelect(miru.Select):
    def __init__(self, *args, **kwargs):
        kwargs['options'] = [
            miru.SelectOption("Mode: FIFO", is_default=True),
            miru.SelectOption("Mode: LIFO"),
            miru.SelectOption("Mode: RANDOM"),
            miru.SelectOption("Mode: INTERLACE")
        ]
        kwargs['placeholder'] = "Mode: FIFO"
        super().__init__(*args, **kwargs)
    
    async def callback(self, ctx):
        self.view.mode = self.values[0].split("Mode: ")[1]


class GoButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.SUCCESS, label="Go!", emoji="▶️")
    
    async def callback(self, ctx):
        if self.view.selection is None:
            await ctx.respond("You did not select a playlist. I need to know which one you want to play.")
        else:
            self.view.proceed = True
        self.view.submitted.set()
        self.view.stop()


class CancelButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.SECONDARY, label="Cancel", emoji="❌")
    
    async def callback(self, ctx):
        await ctx.edit_response(components=[])
        await ctx.respond("Enqueue operation cancelled.")
        self.view.submitted.set()
        self.view.stop()


class EnqueueMenu(miru.View):
    def __init__(self, playlists, *args, **kwargs):
        self.selection = None
        self.shuffle = False
        self.mode = "FIFO"
        self.proceed = False
        self.submitted = asyncio.Event()

        super().__init__(*args, **kwargs)
        self.add_item(PlaylistSelect(playlists))
        self.add_item(ShuffleSelect())
        self.add_item(ModeSelect())
        self.add_item(CancelButton())
        self.add_item(GoButton())
