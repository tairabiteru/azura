from marshmallow import Schema, fields, post_load


class RoleSchema(Schema):
    id = fields.Int(required=True)
    name = fields.Str()
    description = fields.Str(allow_none=True)
    acl = fields.Dict(keys=fields.Str, values=fields.Str)
    rgb = fields.Tuple((fields.Int, fields.Int, fields.Int))

    @post_load
    def make_obj(self, data, **kwargs):
        return Role(**data)


class Role:
    def __init__(self, id, **kwargs):
        self.id = id
        self.name = kwargs["name"] if "name" in kwargs else "unknown"
        self.description = kwargs["description"] if "description" in kwargs else None
        self.acl = kwargs["acl"] if "acl" in kwargs else {}
        self.rgb = kwargs["rgb"] if "rgb" in kwargs else (0, 0, 0)

    def real(self, guild):
        return guild.get_role(self.id)

    def save(self, server):
        for i, role in enumerate(server.roles):
            if role.id == self.id:
                server.roles[i] = self
        server.save()
