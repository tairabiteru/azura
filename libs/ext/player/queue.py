from libs.core.conf import conf
from libs.ext.player.errors import QueueIsEmpty
from libs.ext.utils import ms_as_ts
from libs.orm.songdata import GlobalSongData

import discord
from enum import Enum


class Repeat(Enum):
    NONE = 0
    ONE = 1
    ALL = 2


class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self.repeat_mode = Repeat.NONE

    @property
    def empty(self):
        return not self._queue

    @property
    def current_track(self):
        if self.empty:
            raise QueueIsEmpty

        if self.position <= len(self._queue) - 1:
            return self._queue[self.position]

    def info_embed(self, bot):
        ct = self.current_track
        sde = GlobalSongData.obtain(entry=ct)
        embed = discord.Embed(title=ct.title, colour=discord.Colour(0x14ff), url=f"{ct.uri}")
        _ = embed.set_image(url=ct.thumb) if ct.thumb else None
        embed.set_author(name=conf.name, icon_url=bot.user.avatar_url)
        embed.set_footer(text=conf.name, icon_url=bot.user.avatar_url)
        embed.add_field(name="Duration", value="{}".format(ms_as_ts(ct.length)))
        live = "Yes" if ct.is_stream else "No"
        embed.add_field(name="Author", value=f"{ct.author}")
        embed.add_field(name="Video ID", value=f"{ct.ytid}")
        embed.add_field(name="Global Plays", value=f"{sde.global_plays}")
        embed.add_field(name="Plays by Requester", value=f"{sde.plays_by(uid=ct.requester.id)}")
        embed.add_field(name="Live Stream", value=live)
        return embed

    @property
    def next_tracks(self):
        if self.empty:
            raise QueueIsEmpty

        return self._queue[self.position + 1:]

    @property
    def past_tracks(self):
        if self.empty:
            raise QueueIsEmpty

        return self._queue[:self.position]

    @property
    def length(self):
        return len(self._queue)

    def add(self, *args):
        self._queue.extend(args)

    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty

        self.position += 1

        if self.position < 0:
            return None
        elif self.position > len(self._queue) - 1:
            if self.repeat_mode == Repeat.ALL:
                self.position = 0
            else:
                return None

        return self._queue[self.position]

    def shuffle(self):
        if self.empty:
            raise QueueIsEmpty

        upcoming = self.next_tracks
        random.shuffle(upcoming)
        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)

    def set_repeat_mode(self, mode):
        if mode == "none":
            self.repeat_mode = Repeat.NONE
        elif mode == "one":
            self.repeat_mode = Repeat.ONE
        elif mode == "all":
            self.repeat_mode = Repeat.ALL

    def clear(self):
        self._queue.clear()
        self.position = 0
