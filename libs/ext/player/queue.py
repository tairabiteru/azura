from libs.core.conf import conf
from libs.ext.player.errors import QueueIsEmpty
from libs.ext.player.track import Track
from libs.ext.utils import ms_as_ts, progressBar, url_is_valid
from libs.orm.songdata import GlobalSongData
from libs.orm.playlist import PlaylistEntry

import asyncio
import discord
from enum import Enum
import random


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
        embed.add_field(name="Duration", value="{}".format(ms_as_ts(ct.length)))
        live = "Yes" if ct.is_stream else "No"
        embed.add_field(name="Author", value=f"{ct.author}")
        embed.add_field(name="Video ID", value=f"{ct.ytid}")
        embed.add_field(name="Global Plays", value=f"{sde.global_plays}")
        embed.add_field(name="Plays by Requester", value=f"{sde.plays_by(uid=ct.requester.id)}")
        embed.add_field(name="Requester", value=ct.requester.name)
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

    def add_fifo(self, *args):
        self._queue.extend(args)

    def add_lifo(self, track):
        self._queue.insert(self.position+1, track)

    def add_interlace(self, track, pos, factor):
        position = (pos * factor) + factor
        position = position + self.position
        self._queue.insert(position, track)

    def add_random(self, track):
        self._queue.insert(random.randint(self.position+1, self.length-1), track)

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


class EnqueueJob:
    def __init__(self, ctx, wl, name, playlist, mode="FIFO"):
        self.name = name
        self.ctx = ctx
        self.wl = wl
        self.playlist = playlist
        self.mode = mode
        self.pos = 0
        self.cancel = asyncio.Event()

    @property
    def embed(self):
        if self.pos == len(self.playlist):
            status = f"Enqueued '{self.name}' in {self.mode} Mode"
        else:
            status = f"Enqueueing '{self.name}' in {self.mode} Mode"

        eBar = progressBar(self.pos, len(self.playlist))
        desc = f"`{self.pos} {eBar} {len(self.playlist)}`"
        embed = discord.Embed(title=status, description=desc, colour=discord.Colour(0x14ff))
        embed.add_field(name="Requester", value=self.ctx.author.name)

        if self.pos / len(self.playlist) == 1:
            embed.add_field(name="Progress", value="Done")
        else:
            embed.add_field(name="Progress", value=f"{int(round((float(self.pos) / len(self.playlist)) * 100, 0))}%")

        return embed

    async def execute(self, player):
        successes = []
        failures = []

        factor = []
        for track in player.queue._queue:
            if track.requester.id not in factor:
                factor.append(track.requester.id)
        if self.ctx.author.id not in factor:
            factor.append(self.ctx.author.id)
        factor = len(factor)

        if player.enqmsg is None:
            player.enqmsg = await self.ctx.send(embed=self.embed)

        for i, entry in enumerate(self.playlist):
            if self.cancel.is_set():
                return

            await player.enq_all_clear.wait()
            player.adv_all_clear.clear()

            self.pos += 1

            if isinstance(entry, PlaylistEntry):
                query = entry.generator
                start = entry.start
                end = entry.end
            else:
                query = entry
                start = 0
                end = -1
            if not url_is_valid(query):
                query = f"ytsearch:{query}"

            tracks = await self.wl.get_tracks(query)
            if not tracks:
                failures.append(entry)
                continue

            track = Track(tracks[0], ctx=self.ctx, requester=self.ctx.author, start=start, end=end)
            if self.mode.upper() == "FIFO":
                player.queue.add_fifo(track)
            elif self.mode.upper() == "LIFO":
                player.queue.add_lifo(track)
            elif self.mode.upper() == "INTERLACE":
                player.queue.add_interlace(track, i, factor)
            elif self.mode.upper() == "RANDOM":
                player.queue.add_random(track)
            successes.append(track)

            try:
                last3 = await self.ctx.history(limit=3).flatten()
                if player.enqmsg.id not in [msg.id for msg in last3]:
                    await player.enqmsg.delete()
                    player.enqmsg = await self.ctx.send(embed=self.embed)
                else:
                    await player.enqmsg.edit(embed=self.embed)
            except AttributeError:
                player.enqmsg = await self.ctx.send(embed=self.embed)
            await asyncio.sleep(conf.music.enqueueingShotDelay)

            if not player.is_playing and (player.queue.length == 1 or player.queue.length == player.queue.position + 1):
                await player.start_playback()

            player.adv_all_clear.set()
