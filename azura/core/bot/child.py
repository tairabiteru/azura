from .base import BaseBot

import orjson as json
import websockets


class ChildBot(BaseBot):
    def __init__(self, conf, parent_ws_uri):
        super().__init__(conf)
        self.parent_ws_uri = parent_ws_uri
    
    async def send_to_parent(self, data):
        await self.parent_connection.send(data)

    async def on_ready(self, event):
        await super().on_ready(event)
        self.parent_connection = await websockets.connect(self.parent_ws_uri)
        await self.parent_connection.send(json.dumps({'op': 'init-complete', 'child_name': self.conf.name}))
        self.logger.info("Reporting online to parent.")