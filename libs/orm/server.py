from libs.core.conf import conf
from libs.orm.member import Member

import json
from marshmallow import Schema, fields, post_load
import os

class ServerSchema(Schema):
    id = fields.Int(required=True)
    name = fields.Str()
    timezone = fields.Str(allow_none=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return Server(**data)


class Server:
    def __init__(self, id, **kwargs):
        self.id = id
        self.name = kwargs['name'] if 'name' in kwargs else 'unknown'
        self.timezone = kwargs['timezone'] if 'timezone' in kwargs else "America/Detroit"

        self.members = []

    def complete(self, bot):
        for member in Member.obtain_all():
            if member.uid in [m.id for m in bot.get_guild(self.id).members]:
                self.members.append(member)

    def save(self):
        try:
            os.makedirs(conf.orm.serverDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.serverDir, str(self.id) + ".json"), 'w', encoding='utf-8') as file:
            json.dump(ServerSchema().dump(self), file, sort_keys=True, indent=4, separators=(',', ': '))


class Servers:
    @classmethod
    def obtain(cls, bot, id=None):
        if id:
            try:
                with open(os.path.join(conf.orm.serverDir, str(id) + ".json"), 'r', encoding='utf-8') as file:
                    server = ServerSchema().load(json.load(file))
            except FileNotFoundError:
                server = Server(id)
            server.complete(bot)
            return server
        else:
            servers = []
            for file in os.listdir(conf.orm.serverDir):
                if file.endswith(".json"):
                    with open(os.path.join(conf.orm.serverDir, file), 'w', encoding='utf-8') as file:
                        server = ServerSchema().load(json.load(file))
                        server.complete(bot)
                        servers.append(server)
            return servers

    @classmethod
    def update(cls, bot, guild):
        server = cls.obtain(bot, id=guild.id)
        server.update(guild)
