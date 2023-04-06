import asyncio
import enum
import hikari

from koe.errors import *


MAX_EMBED_QUEUE_DISPLAY = 5


class RepeatMode(enum.Enum):
    NONE = "None"
    ONE = "One"
    ALL = "All"


class Queue:
    def __init__(self):
        self._queue = []
        self._pos = 0
        self._lock = asyncio.Lock()

    async def insert(self, track, position):
        async with self._lock:
            self._queue.insert(position, track)

    async def append(self, track):
        async with self._lock:
            self._queue.append(track)
    
    async def prepend(self, track):
        async with self._lock:
            self._queue.insert(track, self._pos + 1)
    
    def _set_position_to(self, position):
        if position < 0 or position >= len(self._queue):
            raise InvalidPosition(f"Invalid position `{position+1}`. Position must be between 1 and {len(self._queue)} for this queue.")
        self._pos = position

    async def set_position_to(self, position):
        async with self._lock:
            self._set_position_to(position)

    async def get_position(self):
        async with self._lock:
            return self._pos
    
    def _advance_by(self, by):
        new_position = self._pos + by
        if new_position < 0 or new_position >= len(self._queue):
            lower_bnd = -(self._pos) if self._pos != 0 else 1
            upper_bnd = len(self._queue) - (self._pos + 1) if (self._pos + 1) != len(self._queue) else -1
            if lower_bnd == upper_bnd:
                raise InvalidPosition(f"Invalid queue advance: `{by}`. This queue currently can only be advanced by `{lower_bnd}`.")
            raise InvalidPosition(f"Invalid queue advance: `{by}`. The queue currently can only be advanced by values between `{lower_bnd}` and `{upper_bnd}`.")
        self._pos = new_position

    async def advance_by(self, by):
        async with self._lock:
            return self._advance_by(by)

    async def get_all_tracks_list(self):
        async with self._lock:
            return self._queue
    
    def _get_current_tracks_list(self):
        return self._queue[self._pos:]

    async def get_current_tracks_list(self):
        async with self._lock:
            return self._get_current_tracks_list()
    
    async def get_previous_tracks_list(self):
        async with self._lock:
            return self._queue[:self._pos]
    
    def _get_current_track(self):
        return self._get_current_tracks_list()[0]

    async def get_current_track(self):
        async with self._lock:
            return self._get_current_track()

    async def get_last_track(self):
        async with self._lock:
            return self._queue[self._pos-1]
    
    def _get_unique_requesters(self, all_except=[]):
        unique = []
        for trackqueue in self._queue:
            if trackqueue.requester:
                if trackqueue.requester not in unique and trackqueue.requester not in all_except:
                    unique.append(trackqueue.requester)
        return unique
    
    def _is_at_end(self):
        return self._pos + 1 == len(self._queue)

    async def is_at_end(self):
        async with self._lock:
            return self._is_at_end()

    async def is_at_start(self):
        async with self._lock:
            return self._pos == 0

    async def is_empty(self):
        async with self._lock:
            return self._queue == []
    
    # The ANSI escapes cause flashy stuff in Discord, so they're disabled for now.
    # def _get_contents(self, amount=MAX_EMBED_QUEUE_DISPLAY):
    #     contents = "\n"
    #     for i in range(self._pos-amount, self._pos+amount):
    #         if i >= 0:
    #             try:
    #                 if i == self._pos:
    #                     contents += f"\n[2;32m[1;32m{i+1}. 🡲 {self._queue[i].track.info.title} 🡰[0m\n\n"
    #                 elif i < self._pos:
    #                     contents += f"[2;31m{i+1}. {self._queue[i].track.info.title}[0m\n"
    #                 else:
    #                     contents += f"[2;34m{i+1}. {self._queue[i].track.info.title}[0m\n"
    #             except IndexError:
    #                 continue
    #     return f"```ansi{contents}```"

    def _get_contents(self, amount=MAX_EMBED_QUEUE_DISPLAY):
        contents = "\n"
        for i in range(self._pos-amount, self._pos+amount):
            if i >= 0:
                try:
                    if i == self._pos:
                        contents += f"\n{i+1}. 🡲 {self._queue[i].track.info.title} 🡰\n\n"
                    elif i < self._pos:
                        contents += f"{i+1}. {self._queue[i].track.info.title}\n"
                    else:
                        contents += f"{i+1}. {self._queue[i].track.info.title}\n"
                except IndexError:
                    continue
        return f"```{contents}```"
    
    async def get_contents(self, amount=MAX_EMBED_QUEUE_DISPLAY):
        async with self._lock:
            return self._get_contents(amount=amount)
    
    async def get_embed(self, amount=MAX_EMBED_QUEUE_DISPLAY):
        embed = hikari.Embed(title="Current Queue", description="")
        embed.description = await self.get_contents(amount=amount)
        return embed
        
