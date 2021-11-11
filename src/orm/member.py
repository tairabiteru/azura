from core.conf import conf
from orm.profile import Profile, ProfileSchema
from orm.economy import Economy
from ext.utils import localnow

import datetime
import hikari
import json
import Levenshtein
from marshmallow import Schema, fields, post_load
import marshmallow
import operator
import os
import pytz
import random


class MemberSchema(Schema):
    uid = fields.Int(required=True)
    name = fields.Str()
    birthday = fields.Date(allow_none=True)
    timezone = fields.Str(allow_none=True)
    zipcode = fields.Str(allow_none=True)

    last_message_time = fields.DateTime(allow_none=True)
    last_message = fields.Str(allow_none=True)
    next_message_seconds = fields.Int()
    last_voice_time = fields.DateTime(allow_none=True)
    messages_sent = fields.Int()
    characters_typed = fields.Int()
    command_usage = fields.Dict(keys=fields.Str, values=fields.Int)
    voice_connections = fields.Int()

    cookies = fields.Int()
    cookies_eaten = fields.Int()
    cookies_given = fields.Int()
    last_cookie = fields.DateTime()

    yen = fields.Int()
    lastDailies = fields.DateTime(allow_none=True)

    acl = fields.Dict()

    persistent_tts_channel = fields.Int(allow_none=True)
    gtts_language = fields.Str()
    tts_engine = fields.Str()
    user_preface = fields.Boolean()
    caps_overdrive = fields.Boolean()

    sfx_enabled = fields.Boolean()
    sfx = fields.Dict()

    stopwatch = fields.DateTime(allow_none=True)

    stderr_output_channel = fields.Int(allow_none=True)

    profile = fields.Nested(ProfileSchema)

    last_choice_array = fields.List(fields.Str)
    last_choice = fields.Str()
    last_choice_time = fields.DateTime()

    profile_clip = fields.Str(allow_none=True)

    times_spanked = fields.Int()

    successiveCoinFlipWins = fields.Int()

    gachaInventory = fields.List(fields.Str)
    gachaObtained = fields.Int()

    quote = fields.Str()

    craftingDict = fields.Str()

    @post_load
    def make_obj(self, data, **kwargs):
        return Member(**data)


class Member:
    USER_SETTINGS = ["timezone", "zipcode", "profile_clip", "quote", "birthday"]

    @classmethod
    def obtain(cls, uid):
        try:
            with open(
                os.path.join(
                    conf.orm.memberDir, str(uid) + "_" + cls.__name__ + ".json"
                ),
                "r",
                encoding="utf-8",
            ) as file:
                return MemberSchema().load(json.load(file))
        except FileNotFoundError:
            return cls(uid)
        except marshmallow.exceptions.ValidationError as e:
            data = {}
            for key, value in e.data.items():
                if key in e.valid_data:
                    data[key] = value
            return MemberSchema().load(data)

    @classmethod
    def obtain_all(cls):
        members = []
        for root, dirs, files in os.walk(conf.orm.memberDir):
            for file in files:
                if file.endswith(".json"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as file:
                        try:
                            members.append(MemberSchema().load(json.load(file)))
                        except marshmallow.exceptions.ValidationError as e:
                            data = {}
                            for key, value in e.data.items():
                                if key in e.valid_data:
                                    data[key] = value
                            members.append(MemberSchema().load(data))
        return members

    def __init__(self, uid, **kwargs):
        self.uid = uid
        self.name = kwargs["name"] if "name" in kwargs else "unknown"
        self.birthday = kwargs["birthday"] if "birthday" in kwargs else None
        self.timezone = kwargs["timezone"] if "timezone" in kwargs else None
        self.zipcode = kwargs["zipcode"] if "zipcode" in kwargs else None

        self.last_message_time = (
            kwargs["last_message_time"] if "last_message_time" in kwargs else None
        )
        self.last_message = kwargs["last_message"] if "last_message" in kwargs else None
        self.last_voice_time = (
            kwargs["last_voice_time"] if "last_voice_time" in kwargs else None
        )
        self.messages_sent = kwargs["messages_sent"] if "messages_sent" in kwargs else 0
        self.next_message_seconds = (
            kwargs["next_message_seconds"] if "next_message_seconds" in kwargs else 0
        )
        self.characters_typed = (
            kwargs["characters_typed"] if "characters_typed" in kwargs else 0
        )
        self.command_usage = (
            kwargs["command_usage"] if "command_usage" in kwargs else {}
        )
        self.voice_connections = (
            kwargs["voice_connections"] if "voice_connections" in kwargs else 0
        )

        self.cookies = kwargs["cookies"] if "cookies" in kwargs else 0
        self.cookies_eaten = kwargs["cookies_eaten"] if "cookies_eaten" in kwargs else 0
        self.cookies_given = kwargs["cookies_given"] if "cookies_given" in kwargs else 0
        self.last_cookie = (
            kwargs["last_cookie"]
            if "last_cookie" in kwargs
            else localnow() - datetime.timedelta(days=365.25 * 20)
        )

        self.yen = kwargs["yen"] if "yen" in kwargs else 0
        self.lastDailies = (
            kwargs["lastDailies"]
            if "lastDailies" in kwargs
            else localnow() - datetime.timedelta(days=365.25 * 20)
        )

        self.acl = kwargs["acl"] if "acl" in kwargs else {}

        self.persistent_tts_channel = (
            kwargs["persistent_tts_channel"]
            if "persistent_tts_channel" in kwargs
            else None
        )
        self.gtts_language = (
            kwargs["gtts_language"] if "gtts_language" in kwargs else "america"
        )
        self.tts_engine = kwargs["tts_engine"] if "tts_engine" in kwargs else "Google TTS"
        self.user_preface = kwargs['user_preface'] if 'user_preface' in kwargs else False
        self.caps_overdrive = kwargs['caps_overdrive'] if 'caps_overdrive' in kwargs else True

        self.stopwatch = kwargs["stopwatch"] if "stopwatch" in kwargs else None
        self.sfx = kwargs["sfx"] if "sfx" in kwargs else {}
        self.sfx_enabled = kwargs["sfx_enabled"] if "sfx_enabled" in kwargs else True

        self.stderr_output_channel = (
            kwargs["stderr_output_channel"]
            if "stderr_output_channel" in kwargs
            else None
        )

        self.last_choice_array = (
            kwargs["last_choice_array"] if "last_choice_array" in kwargs else []
        )
        self.last_choice = kwargs["last_choice"] if "last_choice" in kwargs else ""
        self.last_choice_time = (
            kwargs["last_choice_time"]
            if "last_choice_time" in kwargs
            else localnow() - datetime.timedelta(days=365.25 * 20)
        )

        self.profile_clip = kwargs["profile_clip"] if "profile_clip" in kwargs else None

        self.times_spanked = kwargs["times_spanked"] if "times_spanked" in kwargs else 0

        self.successiveCoinFlipWins = (
            kwargs["successiveCoinFlipWins"]
            if "successiveCoinFlipWins" in kwargs
            else 0
        )

        self.gachaInventory = (
            kwargs["gachaInventory"] if "gachaInventory" in kwargs else []
        )
        self.gachaObtained = kwargs["gachaObtained"] if "gachaObtained" in kwargs else 0

        self.quote = kwargs["quote"] if "quote" in kwargs else ""

        self.craftingDict = (
            kwargs["craftingDict"] if "craftingDict" in kwargs else "ultimate"
        )

        try:
            self.profile = (
                kwargs["profile"] if "profile" in kwargs else Profile(uid=self.uid)
            )
        except KeyError:
            self.profile = Profile(uid=self.uid)

    @property
    def commands_run(self):
        return sum(self.command_usage.values())

    @property
    def favorite_command(self):
        return max(self.command_usage.items(), key=operator.itemgetter(1))[0]

    @classmethod
    def process_event(cls, bot, event):
        if isinstance(event, hikari.events.message_events.GuildMessageCreateEvent):
            orm = cls.obtain(event.author.id)
            orm.name = event.author.username
            content = event.content if event.content else ""
            if orm.last_message_time is None:
                orm.last_message_time = localnow() - datetime.timedelta(days=365.25 * 20)
            if (localnow() - orm.last_message_time).total_seconds() > orm.next_message_seconds:
                if orm.last_message:
                    if Levenshtein.ratio(content, orm.last_message) < 0.6:
                        orm.next_message_seconds = random.randint(120, 300)
                        orm.yen += Economy.credit(random.randint(10, 50))
            orm.last_message = content
            orm.last_message_time = localnow()
            orm.characters_typed += len(content)
            orm.messages_sent += 1

        elif isinstance(event, hikari.events.voice_events.VoiceStateUpdateEvent):
            orm = cls.obtain(event.state.member.id)
            orm.name = event.state.member.username
            if orm.last_voice_time is None:
                orm.last_voice_time = localnow() - datetime.timedelta(days=365.25 * 20)
            if (localnow() - orm.last_voice_time).total_seconds() > random.randint(1800, 3600):
                orm.yen += Economy.credit(random.randint(250, 500))
            orm.last_voice_time = localnow()
            orm.voice_connections += 1

        else:
            conf.logger.warning(f"Unhandled event type passed to Member.process_event(): {type(event)}")
        orm.save()

    def save(self):
        try:
            os.makedirs(conf.orm.memberDir)
        except FileExistsError:
            pass
        with open(
            os.path.join(
                conf.orm.memberDir,
                str(self.uid) + "_" + self.__class__.__name__ + ".json",
            ),
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                MemberSchema().dump(self),
                file,
                sort_keys=True,
                indent=4,
                separators=(",", ": "),
            )

    def localnow(self):
        return localnow().astimezone(pytz.timezone(self.timezone))

    def isBirthday(self):
        now = self.localnow()
        return now.day == self.birthday.day and now.month == self.birthday.month

    @property
    def TTSMode(self):
        if self.persistent_tts_channel is None:
            return "Command Input"
        elif self.persistent_tts_channel == -1:
            return "DM Input"
        elif self.persistent_tts_channel == -2:
            return "Global Input"
        else:
            return "Channel Input"

    def getProfileEmbed(self, member):
        embed = hikari.embeds.Embed(title=member.username)
        embed.set_thumbnail(member.avatar_url)

        fields = ["birthday", "timezone", "zipcode"]
        for field in fields:
            value = getattr(self, field)
            if value is None:
                value = "Not set"
            embed.add_field(name=field.capitalize(), value=value)

        return embed

    def getAudioEmbed(self, bot, member):
        embed = hikari.embeds.Embed(title=f"__{member.username}'s Audio Settings__")

        if self.TTSMode == "Channel Input":
            channel = bot.cache.get_guild_channel(self.persistent_tts_channel)
            if channel is not None:
                mode = f"Channel Input: {channel.name}"
            else:
                mode = self.TTSMode
        else:
            mode = self.TTSMode

        embed.add_field(name="TTS Mode", value=mode)
        embed.add_field(name="TTS Engine", value=self.tts_engine)
        embed.add_field(name="TTS Language", value=self.gtts_language)
        embed.add_field(name="Overdrive Caps", value=self.caps_overdrive)
        embed.add_field(name="Preface User", value=self.user_preface)
        return embed

    def sfxIsEnabled(self, sfx):
        for line in self.sfx:
            if line.startswith(sfx):
                return True
        return False

    def sfxLine(self, sfx):
        for line in self.sfx:
            if line.startswith(sfx):
                return line
        return None

    def sfxAdd(self, line):
        sfx = line.split(" ")[0]
        if not self.sfxLine(sfx):
            self.sfx.append(line)
        else:
            self.sfx = list([line if l == self.sfxLine(sfx) else l for l in self.sfx])
        self.save()

    @property
    def current_sfx(self):
        output = ""
        for effect in self.sfx:
            effect = effect.split(" ")
            if effect[0] == "echo":
                output += "`echo delay={delay}ms`, ".format(delay=effect[3])
            if effect[0] == "phaser":
                effect[6] = "triangular" if effect[6] == "-t" else "sinusoidal"
                output += "`phaser delay={delay} speed={speed} type={type}`, ".format(
                    delay=effect[3], speed=effect[5], type=effect[6]
                )
            if effect[0] == "chorus":
                effect[7] = "triangular" if effect[7] == "-t" else "sinusoidal"
                output += "`chorus delay={delay} speed={speed} depth={depth} type={type}`, ".format(
                    delay=effect[3], speed=effect[5], depth=effect[6], type=effect[7]
                )
            if effect[0] in ["reverb", "reverse", "loudness", "overdrive", "oops"]:
                output += "`{effect}`, ".format(effect=effect[0])
            if effect[0] == "tremolo":
                output += "`tremolo speed={speed} depth={depth}`, ".format(
                    speed=effect[1], depth=effect[2]
                )
            if effect[0] == "pitch":
                output += "`pitch shift={shift}`, ".format(shift=effect[1])
            if effect[0] == "speed":
                output += "`speed factor={factor}`, ".format(factor=effect[1])
            if effect[0] == "tempo":
                output += "`tempo factor={factor}`, ".format(factor=effect[1])
        return output[:-2]
