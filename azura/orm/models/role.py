from orm.models import HikariModel
from orm.fields import RoleField

import tortoise


class RoleDatum(HikariModel):
    hikari_role = RoleField(pk=True, unique=True)
    acl = tortoise.fields.JSONField(default={})

    @classmethod
    async def get_or_create(cls, role):
        try:
            return await cls.get(hikari_role=role)
        except tortoise.exceptions.DoesNotExist:
            return await cls.create(hikari_role=role)

    @classmethod
    async def get_roles_for_member(cls, user, guild):
        member = await cls.bot.rest.fetch_member(guild, user)
        roles = []
        for role in member.get_roles():
            role = await cls.get_or_create(role)
            roles.append(role)
        return roles
