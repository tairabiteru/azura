from django.db import models
import hikari


class BaseIDField(models.BigIntegerField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class UserIDField(BaseIDField):
    async def aresolve(self, bot, id):
        user = bot.cache.get_user(id)
        if user is None:
            try:
                user = await bot.rest.fetch_user(id)
            except hikari.NotFoundError as e:
                return e
        return user
    
    def resolve(self, bot, id):
        return bot.cache.get_user(id)


class GuildIDField(BaseIDField):
    async def aresolve(self, bot, id):
        guild = bot.cache.get_guild(id)
        if guild is None:
            try:
                guild = await bot.rest.fetch_guild(id)
            except hikari.NotFoundError as e:
                return e
        return guild
    
    def resolve(self, bot, id):
        if not isinstance(id, int):
            id = id.id
        return bot.cache.get_guild(id)


class ChannelIDField(BaseIDField):
    async def aresolve(self, bot, id):
        channel = bot.cache.get_guild_channel(id)
        if channel is None:
            try:
                channel = await bot.rest.fetch_channel(id)
            except hikari.NotFoundError as e:
                return e
        return channel
    
    def resolve(self, bot, id):
        if not isinstance(id, int):
            id = id.id
        return bot.cache.get_guild_channel(id)


class ChannelTypeField(models.CharField):
    TYPES = [
        ('GUILD_TEXT', "Guild - Text"),
        ('GUILD_VOICE', "Guild - Voice")
    ]

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 32
        kwargs['choices'] = ChannelTypeField.TYPES
        super().__init__(*args, **kwargs)


class RoleIDField(BaseIDField):
    async def aresolve(self, bot, id):
        role = bot.cache.get_role(id)
        if role is None:
            for _, guild in bot.cache.get_guilds_view().items():
                roles = await guild.fetch_roles()
                roles = filter(lambda r: r.id == id, roles)
                if len(roles) == 0:
                    raise hikari.NotFoundError(f"The role ID {id} could not be resolved.")
                role = roles[0]
        return role
    
    def resolve(self, bot, id):
        if not isinstance(id, int):
            id = id.id
        return bot.cache.get_role(id)