from ext.location import USLocation
from orm.server import Server

import abc
import hikari
import pytz


class ValidationFailure(Exception):
    """Raised when a setting validator fails."""
    pass


def zipcodeValidator(obj, value):
    location = USLocation(value)
    if location.isvalid:
        return value
    raise ValidationFailure(f"'{value}' is not a valid US zipcode.")


class Setting(abc.ABC):
    TEXT_CHANNELS = hikari.channels.ChannelType.GUILD_TEXT
    VOICE_CHANNELS = hikari.channels.ChannelType.GUILD_VOICE
    # lol make this an enum you dumb bitch
    ROLES = 84912349816531375343123200021564
    BOOLEAN = [True, False]

    def __init__(self):
        self.is_set = False

    @property
    @abc.abstractmethod
    def attr(self) -> str:
        """The name of the attribute in the ORM object."""
        ...

    @property
    def name(self) -> str:
        """The human readable name. If not provided, defaults to attr."""
        return self.attr

    @property
    def values(self):
        """The possible values that are valid for this setting."""
        return None

    @property
    @abc.abstractmethod
    def help(self):
        """The help text for the setting."""
        ...

    @property
    def owner_only(self):
        """Whether or not this setting should be available to anyone but the bot owner."""
        return False

    @property
    def validator(self):
        """A function which validates the setting, or None if no validation is needed."""
        return None

    def validate(self, value):
        if self.validator:
            return self.validator(value)

        try:
            if isinstance(self.values, list):
                if sorted(self.values) == sorted([True, False]):
                    if isinstance(value, str):
                        if value == "True":
                            return True
                        elif value == "False":
                            return False
                        else:
                            raise ValidationFailure(f"'{value}' is not a valid boolean value.")
        except TypeError:
            pass
        if self.use_id:
            if isinstance(value, list):
                value = list(map(int, value))
            else:
                value = int(value)
        return value

    def resolveCurrentValue(self, bot, orm_object):
        """God, I have no idea how the hell this works."""
        self.current = getattr(orm_object, self.attr)
        if isinstance(self.current, list):
            self.multi_selection = True

        if not self.is_set:
            self.use_id = self.values in [Setting.ROLES, Setting.TEXT_CHANNELS, Setting.VOICE_CHANNELS]
            self.is_set = True

        if isinstance(orm_object, Server):
            if self.values in [Setting.TEXT_CHANNELS, Setting.VOICE_CHANNELS]:
                mapping = bot.cache.get_guild(orm_object.id).get_channels()
                if not isinstance(self.current, list):
                    try:
                        self.current = bot.cache.get_guild(orm_object.id).get_channel(self.current)
                    except TypeError:
                        pass
                else:
                    new_current = []
                    for id in self.current:
                        new_current.append(bot.cache.get_guild(orm_object.id).get_channel(id))
                    self.current = new_current
                valid_channels = []
                for id, channel in mapping.items():
                    if channel.type == self.values:
                        valid_channels.append(channel)
                self.values = valid_channels
            elif self.values == Setting.ROLES:
                mapping = bot.cache.get_roles_view_for_guild(orm_object.id)
                if not isinstance(self.current, list):
                    self.current = bot.cache.get_guild(orm_object.id).get_role(self.current)
                else:
                    new_current = []
                    for id in self.current:
                        new_current.append(bot.cache.get_guild(orm_object.id).get_role(id))
                    self.current = new_current
                roles = []
                for id, role in mapping.items():
                    if role.name != "@everyone":
                        roles.append(role)
                self.values = roles


class SettingContainer(abc.ABC):
    settings = []

    def __init__(self, orm_object):
        self.orm_object = orm_object

    @property
    @abc.abstractmethod
    def settings(self):
        ...

    @classmethod
    def setting(cls, setting):
        cls.settings.append(setting())

        def wrapper(setting):
            return setting
        return wrapper

    def resolveCurrentValues(self, bot):
        for setting in self.__class__.settings:
            setting.resolveCurrentValue(bot, self.orm_object)

    def getSetting(self, setting_name):
        for setting in self.__class__.settings:
            if setting.attr == setting_name:
                return setting

    def setSetting(self, setting, value):
        value = setting.validate(value)
        setattr(self.orm_object, setting.attr, value)
        self.orm_object.save()

    @classmethod
    def obtain(cls, bot, orm_object):
        settings = cls(orm_object)
        settings.resolveCurrentValues(bot)
        # Calling this twice fixes some stuff
        # It's been 7 hours. Kill me.
        # Might actually be cache bullshit, iunno.
        settings.resolveCurrentValues(bot)
        return settings


class ServerSettings(SettingContainer):
    settings = []


@ServerSettings.setting
class ServerTimezone(Setting):
    attr = 'timezone'
    name = 'Timezone'
    values = pytz.all_timezones
    help = "The timezone the server is in."


class MemberSettings(SettingContainer):
    settings = []


@MemberSettings.setting
class MemberTimezone(Setting):
    attr = 'timezone'
    name = 'Timezone'
    values = pytz.all_timezones
    help = "The timezone you live in. Setting this can make time related commands more accurate."
