from core.conf import conf
from ext.utils import utcnow
import orm.models as models
import orm.fields as fields

import hikari
import pytz
import tortoise


class Guild(models.HikariModel):
    hikari_guild = fields.GuildField(pk=True, unique=True)
    timezone = fields.TimezoneField(default=conf.timezone)

    roledata = tortoise.fields.ManyToManyField("models.RoleDatum")

    @classmethod
    async def get_or_create(cls, guild):
        try:
            return await cls.get(hikari_guild=guild)
        except tortoise.exceptions.DoesNotExist:
            return await cls.create(hikari_guild=guild)

    @classmethod
    async def process_event(cls, event):
        guild = await cls.get_or_create(event.guild_id)

        if isinstance(event, hikari.RoleDeleteEvent) or isinstance(event, hikari.RoleCreateEvent):
            await guild.update_roles()
        else:
            raise ValueError(f"Event of type {type(event)} in GID {guild.hikari_guild.id} was passed to process_event, which is unsupported.")
        await guild.save()

    def localnow(self):
        return utcnow().astimezone(self.timezone)

    async def update_roles(self):
        for id, role in self.hikari_guild.get_roles().items():
            roles = await self.roledata.all().filter(hikari_role=role)
            if not roles:
                role = await models.RoleDatum.get_or_create(role)
                await self.roledata.add(role)

        roledatums = await self.roledata.all()
        for roledatum in roledatums:
            if roledatum.hikari_role.id not in [r.id for r in self.hikari_guild.get_roles().values()]:
                await self.roledata.remove(roledatum)
                await roledatum.delete()

    async def get_members(self):
        members = []
        for member in self.hikari_guild.get_members().values():
            member = await models.User.get_or_create(member.user)
            members.append(member)
        return members

    async def get_settings(self):
        settings = [
            models.UISetting("Timezone", "timezone", "enum", str(self.timezone), "The timezone the server operates in.", options=pytz.all_timezones),
        ]
        return settings

    async def set_settings(self, json):
        await self.select_for_update()

        async with models.DBTransaction(connection_name="default"):
            if json['setting'] == "timezone":
                self.timezone = pytz.timezone(json['value'])
            else:
                print(json)
            await self.save()
