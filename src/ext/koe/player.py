import asyncio


class NowPlayingMessage:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._msg = None

    async def update(self):
        pass
