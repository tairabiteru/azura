from core.conf import conf

from koe.session.base import Session
from koe.enums import EnqueueMode, RepeatMode
from koe.errors import InvalidResponse, SessionBusy

import aiohttp
import hikari


def endpoint(func):
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        if 'status' in response:
            if response['status'] == 'OK':
                return response
            elif response['status'] == 'BUSY':
                raise SessionBusy
            else:
                raise InvalidResponse(response)
        else:
            raise InvalidResponse(response)
    return wrapper


class RemoteSession(Session):
    def __init__(self, child_name, *args):
        self.child_name = child_name

        child_conf = conf.get_bot(child_name)
        self.endpoint = f"http://{child_conf.host}:{child_conf.port}"

        super().__init__(*args)
    
    @endpoint
    async def _connect(self):
        return await self._post("/api/connect", self.serialized)

    @endpoint
    async def _disconnect(self):
        return await self._post("/api/disconnect", self.serialized)

    async def _post(self, path, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.endpoint}{path}", json=data, headers={'Content-Type': 'application/json'}) as response:
                response = await response.json()
        return response
    
    # --- BEGIN ENDPOINT DEFINITIONS ---
    @endpoint
    async def display_playback(self):
        return await self._post("/api/display_playback", self.serialized)
    
    @endpoint
    async def display_queue(self):
        return await self._post("/api/display_queue", self.serialized)
    
    @endpoint
    async def enqueue(self, requester: hikari.User, playlist: str, shuffle: bool=False, mode: str="FIFO", user: hikari.User=None):
        data = self.serialized
        data['requester_id'] = requester.id
        data['playlist'] = playlist
        data['shuffle'] = shuffle
        data['mode'] = mode
        data['user_id'] = user.id if user is not None else None

        return await self._post("/api/enqueue", data)
    
    @endpoint
    async def pause(self):
        return await self._post("/api/pause", self.serialized)

    @endpoint
    async def play(self, requester: hikari.User, query: str, position: int=-1):
        data = self.serialized
        data['query'] = query
        data['requester_id'] = requester.id
        data['position'] = position

        return await self._post("/api/play", data)

    @endpoint
    async def set_repeat_mode(self, setting: RepeatMode):
        data = self.serialized
        data['setting'] = setting.value

        return await self._post("/api/repeat_mode/set", data)
    
    @endpoint
    async def set_volume(self, user, setting=None, increment=None):
        data = self.serialized
        data['user_id'] = user.id
        data['setting'] = setting
        data['increment'] = increment

        return await self._post("/api/volume/set", data)
    
    @endpoint
    async def skip(self, requester: hikari.User, to: int=None, by: int=None):
        data = self.serialized
        data['to'] = to
        data['by'] = by
        data['requester_id'] = requester.id

        return await self._post("/api/skip", data)