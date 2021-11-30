import asyncio


class QueueIsEmpty(Exception):
    """Raised when the queue is accessed while empty."""
    pass


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

    async def currentTracks(self):
        async with self._lock:
            return self._queue[self._pos:]

    async def isEnd(self):
        async with self._lock:
            return self._pos+1 == len(self._queue)

    async def isStart(self):
        async with self._lock:
            return self._pos == 0
