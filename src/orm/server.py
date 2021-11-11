from core.conf import conf
from ext.utils import localnow
from ext.starboard import StarredMessage
from orm.roles import RoleSchema, Role
from orm.member import Member
from orm.autism import AutismRecord, AutismRecordSchema

import datetime
import hikari
import json
from marshmallow import Schema, fields, post_load
import os


class Record:
    def __init__(self, stamp):
        self.stamp = stamp

    @property
    def time(self):
        return datetime.datetime.strptime(self.stamp.split(" ")[0], "%x-%X%z")

    @property
    def id(self):
        return int(self.stamp.split(" ")[1])

    @property
    def event(self):
        return self.stamp.split(" ")[2]


class ServerSchema(Schema):
    id = fields.Int(required=True)
    name = fields.Str()
    timezone = fields.Str(allow_none=True)
    log_channel = fields.Int(allow_none=True)

    roles = fields.List(fields.Nested(RoleSchema))

    allowProfileClips = fields.Boolean()

    starboardChannel = fields.Int(allow_none=True)
    starboardRoles = fields.List(fields.Int)
    starboardEmoji = fields.Str()
    starboardMessage = fields.Str()

    nicklocked_members = fields.Dict(keys=fields.Str, values=fields.Str)
    profile_clip_banned_channels = fields.Dict(keys=fields.Str, values=fields.Int)

    trackActivity = fields.Boolean()
    activityLogThreshold = fields.Int()
    activityRoleId = fields.Int(allow_none=True)

    autismChannel = fields.Int(allow_none=True)
    autismRecords = fields.List(fields.Nested(AutismRecordSchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return Server(**data)


class Server:
    def __init__(self, id, **kwargs):
        self.id = id
        self.name = kwargs["name"] if "name" in kwargs else "unknown"
        self.timezone = (
            kwargs["timezone"] if "timezone" in kwargs else "America/Detroit"
        )
        self.log_channel = kwargs["log_channel"] if "log_channel" in kwargs else None
        self.roles = kwargs["roles"] if "roles" in kwargs else []

        self.allowProfileClips = (
            kwargs["allowProfileClips"] if "allowProfileClips" in kwargs else False
        )

        self.starboardChannel = (
            kwargs["starboardChannel"] if "starboardChannel" in kwargs else None
        )
        self.starboardRoles = (
            kwargs["starboardRoles"] if "starboardRoles" in kwargs else []
        )
        self.starboardEmoji = kwargs['starboardEmoji'] if 'starboardEmoji' in kwargs else "⭐🌟🌠"
        self.starboardMessage = kwargs['starboardMessage'] if 'starboardMessage' in kwargs else "☄️ Among the Stars ☄️"

        self.nicklocked_members = (
            kwargs["nicklocked_members"] if "nicklocked_members" in kwargs else {}
        )
        self.profile_clip_banned_channels = (
            kwargs["profile_clip_banned_channels"]
            if "profile_clip_banned_channels" in kwargs
            else {}
        )

        self.trackActivity = (
            kwargs["trackActivity"] if "trackActivity" in kwargs else False
        )
        self.activityLogThreshold = (
            kwargs["activityLogThreshold"]
            if "activityLogThreshold" in kwargs
            else 100000
        )
        self.activityRoleId = (
            kwargs["activityRoleId"] if "activityRoleId" in kwargs else None
        )

        self.autismChannel = kwargs['autismChannel'] if 'autismChannel' in kwargs else None
        self.autismRecords = kwargs['autismRecords'] if 'autismRecords' in kwargs else []

    @classmethod
    def obtain(cls, id):
        try:
            with open(
                os.path.join(conf.orm.serverDir, f"{id}.json"), "r", encoding="utf-8"
            ) as file:
                server = ServerSchema().load(json.load(file))
        except FileNotFoundError:
            server = cls(id)
        return server

    @classmethod
    def obtain_all(cls):
        servers = []
        for file in os.listdir(conf.orm.serverDir):
            if file.endswith(".json"):
                server = cls.obtain(file.split(".")[0])
                servers.append(server)
        return servers

    @classmethod
    async def process_event(cls, bot, event):
        server = cls.obtain(event.guild_id)
        if isinstance(event, hikari.events.message_events.GuildMessageCreateEvent):
            if event.author.is_bot:
                return

            if not server.trackActivity:
                return

            act = server.getActivity()
            if len(act) >= server.activityLogThreshold:
                act = act[-(server.activityLogThreshold - 1):]
            act.append(f"{localnow().strftime('%x-%X%z')} {event.author.id} message")
            server.saveActivity(act)
            await server.checkActive(bot, event.author.id)

        elif isinstance(event, hikari.GuildReactionAddEvent):
            if StarredMessage.checkEvent(bot, event, server):
                embed = await StarredMessage.fromEvent(bot, event).getEmbed()
                await bot.rest.create_message(server.starboardChannel,
                    server.starboardMessage,
                    embed=embed
                )
        elif isinstance(event, hikari.RoleCreateEvent) or isinstance(event, hikari.RoleDeleteEvent) or isinstance(event, hikari.RoleUpdateEvent):
            guild = bot.cache.get_guild(event.guild_id)
            server.update(guild)
        elif isinstance(event, hikari.MemberCreateEvent):
            if not event.member.is_bot:
                for role in server.roles:
                    if role.autoAssign:
                        await event.member.add_role(role.id)
        else:
            conf.logger.warning(f"Unhandled event type passed to Server.process_event(): {type(event)}")

    @property
    def tags(self):
        return list([role for role in self.roles if role.is_tag])

    def getTagRoles(self, bot):
        return [bot.cache.get_role(tag.id) for tag in self.tags]

    @property
    def tagDelimiter(self):
        for role in self.roles:
            if role.is_tag_delimiter:
                return role
        return None

    def getTagDelimiter(self, bot):
        return bot.cache.get_role(self.tagDelimiter.id) if self.tagDelimiter is not None else None

    def getActivity(self):
        try:
            with open(os.path.join(conf.orm.serverDir, f"{self.id}.act"), "r") as act:
                return list([record.replace("\n", "") for record in act.readlines()])
        except FileNotFoundError:
            return []

    @property
    def activities(self):
        return map(Record, self.getActivity())

    def saveActivity(self, activity):
        act = open(os.path.join(conf.orm.serverDir, f"{self.id}.act"), "w")
        if all([isinstance(a, Record) for a in activity]):
            act.writelines([f"{record.stamp}\n" for record in activity])
        elif all([isinstance(a, str) for a in activity]):
            act.writelines([f"{record}\n" for record in activity])
        else:
            raise ValueError(
                "Mixed typing detected in activity list. Must be all str or Record."
            )
        act.close()

    def getMembers(self, bot):
        members = []
        for member in Member.obtain_all():
            if member.uid in [m.id for m in bot.cache.get_available_guild(self.id).get_members().values()]:
                members.append(member)
        return members

    def percent_active(self, id):
        if len(self.getActivity()) == 0:
            return 0.0
        return round(
            (
                float(
                    len(list([record for record in self.activities if record.id == id]))
                )
                / len(self.getActivity())
            )
            * 100,
            2,
        )

    def is_active_member(self, bot, id):
        threshold = ((1.0 / len(self.getMembers(bot))) * 100) - 1
        return self.percent_active(id) >= threshold

    async def checkActive(self, bot, id):
        member = bot.cache.get_member(self.id, id)
        if self.activityRoleId is not None:
            if self.is_active_member(bot, id):
                if self.activityRoleId not in member.role_ids:
                    await member.add_role(self.activityRoleId)
            else:
                if self.activityRoleId in member.role_ids:
                    await member.remove_role(self.activityRoleId)

    async def checkAutismLevels(self, bot):
        if self.autismChannel is not None:
            channel = await bot.rest.fetch_channel(self.autismChannel)
            if channel is None:
                raise ValueError(f"Invalid channel for guild #{self.id}: {self.autismChannel}.")

            record = await AutismRecord.buildFromChannel(channel)
            self.autismRecords.append(record)
            self.save()

    def statefulTags(self, member):
        tags = []
        roles = member.get_roles()
        for tag in self.tags:
            if tag.id in [role.id for role in roles]:
                tag.enabled = True
            else:
                tag.enabled = False
            tags.append(tag)
        tags = sorted(tags, key=lambda x: x.name)
        return tags

    def update(self, guild):
        new_roles = []
        for id, role in guild.get_roles().items():
            if role.id not in [r.id for r in self.roles]:
                new_roles.append(Role(role.id, name=role.name, rgb=role.color.rgb))
            else:
                r = next((r for r in self.roles if r.id == role.id), None)
                r.name = role.name
                r.rgb = role.color.rgb
                new_roles.append(r)
        self.roles = new_roles

        self.name = guild.name

        self.save()

    def get_role(self, id):
        for role in self.roles:
            if role.id == id:
                return role
        else:
            return None

    def save(self):
        try:
            os.makedirs(conf.orm.serverDir)
        except FileExistsError:
            pass
        with open(
            os.path.join(conf.orm.serverDir, str(self.id) + ".json"),
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                ServerSchema().dump(self),
                file,
                sort_keys=True,
                indent=4,
                separators=(",", ": "),
            )

    def getAutismRecords(self, since=None, to=None):
        try:
            since = since if since is not None else self.autismRecords[0].timestamp
            to = to if to is not None else localnow()
        except IndexError:
            raise ValueError("There are no autism records available.")

        records = []
        for record in self.autismRecords:
            if record.timestamp >= since and record.timestamp <= to:
                records.append(record)
        return records

    def getRecords(self, since=None, to=None):
        return self.getAutismRecords(since=since, to=to)


class Servers:
    @classmethod
    def obtain(cls, id=None):
        if id:
            try:
                with open(
                    os.path.join(conf.orm.serverDir, str(id) + ".json"),
                    "r",
                    encoding="utf-8",
                ) as file:
                    server = ServerSchema().load(json.load(file))
            except FileNotFoundError:
                server = Server(id)
            return server
        else:
            servers = []
            for file in os.listdir(conf.orm.serverDir):
                if file.endswith(".json"):
                    with open(
                        os.path.join(conf.orm.serverDir, file), "r", encoding="utf-8"
                    ) as file:
                        server = ServerSchema().load(json.load(file))
                        servers.append(server)
            return servers

    @classmethod
    def update(cls, bot, guild):
        server = cls.obtain(guild.id)
        server.update(guild)
