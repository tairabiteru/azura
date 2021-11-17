from core.conf import conf
from ext.utils import localnow

import json
from marshmallow import Schema, fields, post_load
import marshmallow
import os
import pytz


class MemberSchema(Schema):
    uid = fields.Int(required=True)
    name = fields.Str()
    timezone = fields.Str(allow_none=True)

    acl = fields.Dict()

    @post_load
    def make_obj(self, data, **kwargs):
        return Member(**data)


class Member:
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
        self.timezone = kwargs["timezone"] if "timezone" in kwargs else None

        self.acl = kwargs["acl"] if "acl" in kwargs else {}

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
