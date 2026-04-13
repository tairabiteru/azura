import lavalink_rs as lavalink
from lavalink_rs.model import events

from ...core.log import logging


logger = logging.getLogger("koe")


class KoeEventHandler(lavalink.EventHandler):
    async def ready(
        self,
        client: lavalink.LavalinkClient,
        session_id: str,
        event: events.Ready
    ) -> None:
        del client, session_id, event
        logger.info("Voice engine started.")
    
    async def track_start(
        self,
        client: lavalink.LavalinkClient,
        session_id: str,
        event: events.TrackStart
    ) -> None:
        del session_id
        
        logger.info(f"Track {event.track.info.author} - {event.track.info.title} in {event.guild_id.inner}")
        ctx = client.get_player_context(event.guild_id.inner)
        print(ctx)