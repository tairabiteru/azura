from .base import BaseSession
from ..objects import RepeatMode, EnqueueMode

import orjson as json
import typing


class RemoteSession(BaseSession):
    def __init__(self, hanabi, guild_id: int, voice_id: int, channel_id: int, child):
        BaseSession.__init__(self, hanabi, guild_id, voice_id, channel_id)
        self.child = child
    
    @property
    def child_connection(self):
        return self.hanabi.bot.get_child_connection(self.child)

    async def send_to_child(self, data):
        await self.child_connection.send(json.dumps(data))
        resp = await self.child_connection.recv()
        return json.loads(resp.decode("utf-8"))
    
    async def play_cmd(self, title, requester, position=-1):
        await self.send_to_child({'op': 'play', 'voice_id': self.voice_id, 'title': title, 'requester': requester, 'position': position})
    
    async def disconnect(self):
        await self.send_to_child({'op': 'disconnect', 'voice_id': self.voice_id})
    
    async def skip(self, to=None, by=None):
        await self.send_to_child({'op': 'skip', 'voice_id': self.voice_id, 'by': by, 'to': to})
    
    async def volume_cmd(self, setting):
        await self.send_to_child({'op': 'volume', 'voice_id': self.voice_id, 'setting': setting})
    
    async def set_repeat_mode(self, mode: RepeatMode):
        await self.send_to_child({'op': 'repeat-mode', 'voice_id': self.voice_id, 'mode': mode.value})
    
    async def enqueue_cmd(self, name: str, owner: int, requester: int, shuffle: bool = False, mode: EnqueueMode = EnqueueMode.FIFO, bypass_owner: bool = False):
        await self.send_to_child({
            'op': 'enqueue',
            'voice_id': self.voice_id,
            'name': name,
            'owner': owner,
            'requester': requester,
            'shuffle': shuffle,
            'mode': mode.value,
            'bypass_owner': bypass_owner
        })
    
    async def display_queue(self, amount=20):
        await self.send_to_child({
            'op': 'display-queue',
            'voice_id': self.voice_id,
            'amount': amount
        })
    
    async def dequeue_cmd(self, positions: typing.List[int] = None, requester: typing.Optional[int] = None):
        await self.send_to_child({
            'op': 'dequeue',
            'voice_id': self.voice_id,
            'positions': positions,
            'requester': requester
        })
    
    async def on_track_start(self, event):
        async with self.lock:
            self._is_playing = True

    async def on_track_end(self, event):
        async with self.lock:
            self._is_playing = False
            if event.may_start_next:
                if self._repeat_mode is RepeatMode.ONE:
                    await self.dplay()
                else:
                    track = self.dadvance()
                    if self._repeat_mode is RepeatMode.NONE:
                        if track is not None:
                            await self.dplay()
                    elif self._repeat_mode is RepeatMode.ALL:
                        if track is None:
                            self.dadvance_to(1)
                        await self.dplay()
    
    async def on_player_update(self, event):
        print(event)


    

