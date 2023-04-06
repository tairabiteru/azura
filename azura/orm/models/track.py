import orm.models as models
import orm.fields as fields

import tortoise


class TrackHistoryRecord(models.HikariModel):
    guild = fields.GuildField()
    requester = fields.UserField()
    timestamp = tortoise.fields.DatetimeField(auto_now=True)
    source = tortoise.fields.TextField()
    title = tortoise.fields.TextField()
    author = tortoise.fields.TextField()
    length = tortoise.fields.IntField()

    @classmethod
    async def from_track_start_event(cls, event, session):
        # guild = session.bot.cache.get_guild(event.guild_id)
        # track_info = await session.lavalink.decode_track(event.track)
        pass

