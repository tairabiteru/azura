from core.conf import conf
from orm.roles import RoleSchema, Role

import json
from marshmallow import Schema, fields, post_load
import os


class ServerSchema(Schema):
    id = fields.Int(required=True)
    name = fields.Str()
    timezone = fields.Str(allow_none=True)

    roles = fields.List(fields.Nested(RoleSchema))

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
        self.roles = kwargs["roles"] if "roles" in kwargs else []

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
