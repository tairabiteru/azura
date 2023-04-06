import orm.models as models

import tortoise


class HikariMixin:
    def __init__(self, *args, **kwargs):
        self.bot = None


class UserField(tortoise.fields.BigIntField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        if isinstance(value, models.User):
            return value.hikari_user.id
        elif isinstance(value, int):
            return value
        return value.id

    def to_python_value(self, value):
        if isinstance(value, models.User):
            return value.hikari_user
        elif value is not None:
            user = self.bot.cache.get_user(value)
            return user  


class UserArrayField(tortoise.fields.JSONField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        return None if value is None else self.encoder(list([val.id for val in value]))

    def to_python_value(self, value):
        users = list([self.bot.cache.get_user(val) for val in self.decoder(value)])
        if any([user is None for user in users]):
            raise ValueError(f"Deserialization failed for UIDs {value}. Not found in cache.")
        return users


class GuildField(tortoise.fields.BigIntField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        if value is not None:
            if isinstance(value, int):
                if len(str(value)) != 18:
                    raise ValueError(f"Serialization failed for value {value}. Not a valid GID.")
                return value
            return value.id

    def to_python_value(self, value):
        if value is not None:
            user = self.bot.cache.get_guild(value)
            if user is None:
                raise ValueError(f"Deserialization failed for GID {value}. Not found in cache.")
            return user


class GuildArrayField(tortoise.fields.JSONField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        return None if value is None else self.encoder(list([val.id for val in value]))

    def to_python_value(self, value):
        guilds = list([self.bot.cache.get_guild(val) for val in self.decoder(value)])
        if any([guild is None for guild in guilds]):
            raise ValueError(f"Deserialization failed for GIDs {value}. Not found in cache.")
        return guilds


class ChannelField(tortoise.fields.BigIntField, HikariMixin):
    def __init__(self, *args, **kwargs):
        if "channel_type" in kwargs:
            self.channel_type = kwargs.pop("channel_type")
        else:
            self.channel_type = None

        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        if value is not None:
            if self.channel_type is not None:
                if value.type != self.channel_type:
                    raise ValueError(f"Serialization failed for CID {value.id}. Channel constraint {self.channel_type} does not match channel type of {value.type}.")
            return value.id

    def to_python_value(self, value):
        if value is not None:
            channel = self.bot.cache.get_guild_channel(value)
            if channel is None:
                raise ValueError(f"Deserialization failed for CID {value}. Not found in cache.")
            return channel


class ChannelArrayField(tortoise.fields.JSONField, HikariMixin):
    def __init__(self, *args, **kwargs):
        if "channel_types" in kwargs:
            self.channel_types = kwargs.pop("channel_types")
        else:
            self.channel_types = []

        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        if self.channel_types != []:
            for channel in value:
                if channel is not None:
                    if channel.type not in self.channel_types:
                        raise ValueError(f"Serialization failed for channels {value}. One or more of the channel types does not match the channel constraints of {self.channel_types}.")
        return None if value is None else self.encoder(list([val.id for val in value]))

    def to_python_value(self, value):
        channels = list([self.bot.cache.get_guild_channel(val) for val in self.decoder(value)])
        return channels


class RoleField(tortoise.fields.BigIntField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        if value is not None:
            return value.id

    def to_python_value(self, value):
        if value is not None:
            role = self.bot.cache.get_role(value)
            if role is None:
                raise ValueError(f"Deserialization failed for RID {value}. Not found in cache.")
            return role


class RoleArrayField(tortoise.fields.JSONField, HikariMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

    def to_db_value(self, value, instance):
        return None if value is None else self.encoder(list([val.id for val in value]))

    def to_python_value(self, value):
        if value is None:
            return None
        roles = list([self.bot.cache.get_role(val) for val in self.decoder(value)])
        if any([role is None for role in roles]):
            raise ValueError(f"Deserialization failed for RIDs {value}. Not found in cache.")
        return roles
