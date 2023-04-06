from ext.utils import utcnow
import orm.models as models
import orm.fields as fields

import pytz
import tortoise


class User(models.HikariModel):
    hikari_user = fields.UserField(pk=True, unique=True)
    timezone = fields.TimezoneField(default=pytz.timezone("UTC"))
    acl = tortoise.fields.data.JSONField(default={})

    volume_step = tortoise.fields.IntField(default=5)
    prompt_on_Search = tortoise.fields.BooleanField(default=True)
    last_volume = tortoise.fields.IntField(default=100)
    playlists = tortoise.fields.ManyToManyField("models.Playlist")

    @classmethod
    async def get_or_create(cls, user):
        try:
            return await cls.get(hikari_user=user)
        except tortoise.exceptions.DoesNotExist:
            return await cls.create(hikari_user=user)
    
    async def create_playlist(self, name, description="No description provided.", is_public=False):
        playlist = await models.Playlist.create(
            owner=self.hikari_user,
            name=name,
            description=description,
            is_public=is_public
        )
        await playlist.save()

        await self.playlists.add(playlist)
        await self.save()
        return playlist

    def localnow(self):
        return utcnow().astimezone(self.timezone)

    async def get_settings(self):
        settings = [
            models.UISetting("Timezone", "timezone", "enum", str(self.timezone), "The timezone you reside in.", options=pytz.all_timezones),
        ]
        return settings

    async def set_settings(self, json):
        await self.select_for_update()

        async with models.DBTransaction(connection_name="default"):
            if json['setting'] == "timezone":
                self.timezone = pytz.timezone(json['value'])
            await self.save()
