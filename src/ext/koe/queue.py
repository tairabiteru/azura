import asyncio
import hikari


class PositionError(Exception):
    """Raised when a queue is set to an invalid position."""
    pass


class KoeQueue:
    """
    Implementation of a threadsafe queue.

    I mean, it's maybe threadsafe, lol iunno
    """
    def __init__(self):
        self._queue = []
        self._pos = 0
        self._lock = asyncio.Lock()

    async def insert(self, track, pos):
        async with self._lock:
            self._queue.insert(pos, track)

    async def append(self, track):
        async with self._lock:
            self._queue.append(track)

    async def set_pos(self, pos):
        async with self._lock:
            if pos < 0 or pos >= len(self._queue):
                raise PositionError(f"Invalid position: `{pos+1}`. Position must be between 1 and {len(self._queue)} for this queue.")
            self._pos = pos

    async def pos(self):
        async with self._lock:
            return self._pos

    async def move(self, by):
        async with self._lock:
            new_pos = self._pos
            new_pos += by
            if new_pos < 0 or new_pos >= len(self._queue):
                lower_bnd = -(self._pos) if self._pos != 0 else 1
                upper_bnd = len(self._queue) - (self._pos + 1) if (self._pos+1) != len(self._queue) else -1
                if lower_bnd == upper_bnd:
                    raise PositionError(f"Invalid queue movement: `{by}`. This queue currently can only be moved by `{lower_bnd}`.")
                raise PositionError(f"Invalid queue movement: `{by}`. This queue's movements currently must be between `{lower_bnd}` and `{upper_bnd}`")
            self._pos = new_pos

    async def queue(self):
        async with self._lock:
            return self._queue

    async def getQueueEmbed(self, forward=10, backward=10):
        async with self._lock:
            embed = hikari.embeds.Embed(title="Current Queue")
            desc = ""

            for i, track in enumerate(self._queue):
                if i == self._pos:
                    desc += f"\n❯ {track.track.info.title} ❮\n\n"
                elif i >= (self._pos - backward) or i <= (self._pos + forward):
                    position = self._pos + i if self._pos != 0 else 1
                    desc += f"{position}. {track.track.info.title}\n"
            embed.description = f"```{desc}```"
            return embed

    async def currentTracks(self):
        async with self._lock:
            return self._queue[self._pos:]

    async def currentTrack(self):
        return (await self.currentTracks())[0]

    async def isEnd(self):
        async with self._lock:
            return self._pos+1 == len(self._queue)

    async def isStart(self):
        async with self._lock:
            return self._pos == 0

    async def isEmpty(self):
        async with self._lock:
            return self._queue == []
