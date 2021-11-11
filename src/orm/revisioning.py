from core.conf import conf
from ext.utils import localnow

import json
import hashlib
import os
from marshmallow import Schema, fields, post_load


def get_lines(path):
    lines = 0
    for subdir, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(subdir, file), "r") as f:
                    for line in f:
                        lines += 1
    return lines


def get_hash(path):
    libfiles = []
    for subdir, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                libfiles.append(os.path.join(subdir, file))

    hash = hashlib.sha512(open(libfiles[0], "rb").read())
    for file in libfiles[1:]:
        hash.update(open(file, "rb").read())
    return hash.hexdigest()


class RevisionSchema(Schema):
    hash = fields.Str(required=True)
    lines = fields.Int(required=True)
    chars = fields.Int(required=True)
    files = fields.Int(required=True)
    size = fields.Int(required=True)
    number = fields.Int(required=True)
    major_version = fields.Str(required=True)
    version_tag = fields.Str(required=True)
    timestamp = fields.DateTime(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return Revision(**data)


class Revision:
    def __init__(self, **kwargs):
        if (
            ("hash" not in kwargs)
            or ("lines" not in kwargs)
            or ("chars" not in kwargs)
            or ("files" not in kwargs)
            or ("size" not in kwargs)
        ):
            libfiles = []
            lines = 0
            chars = 0
            fs = 0
            size = 0
            for subdir, dirs, files in os.walk(conf.rootDir):
                for file in files:
                    fs += 1
                    size += os.path.getsize(os.path.join(subdir, file))
                    if file.endswith(".py"):
                        libfiles.append(os.path.join(subdir, file))
                        with open(os.path.join(subdir, file), "r") as f:
                            for line in f:
                                lines += 1
                                chars += len(line)

            hash = hashlib.sha512(open(libfiles[0], "rb").read())
            for file in libfiles[1:]:
                hash.update(open(file, "rb").read())
            hash = hash.hexdigest()

        self.hash = kwargs["hash"] if "hash" in kwargs else hash
        self.lines = kwargs["lines"] if "lines" in kwargs else lines
        self.chars = kwargs["chars"] if "chars" in kwargs else chars
        self.files = kwargs["files"] if "files" in kwargs else fs
        self.size = kwargs["size"] if "size" in kwargs else size
        self.number = (
            kwargs["number"]
            if "number" in kwargs
            else Revisioning.obtain().current.number + 1
        )
        self.major_version = (
            kwargs["major_version"] if "major_version" in kwargs else conf.VERSION
        )
        self.version_tag = (
            kwargs["version_tag"] if "version_tag" in kwargs else conf.VERSIONTAG
        )
        self.timestamp = kwargs["timestamp"] if "timestamp" in kwargs else localnow()

    def isLatest(self):
        revisioning = Revisioning.obtain()
        if revisioning.current.timestamp == self.timestamp:
            return True
        return False

    def __str__(self):
        return (
            self.major_version
            + " R."
            + str(self.number)
            + " '"
            + self.version_tag
            + "'"
        )


class RevisioningSchema(Schema):
    revisions = fields.List(fields.Nested(RevisionSchema))
    current = fields.Nested(RevisionSchema)

    @post_load
    def make_obj(self, data, **kwargs):
        return Revisioning(**data)


class Revisioning:
    @classmethod
    def obtain(cls):
        try:
            with open(
                os.path.join(conf.orm.botDir, "revisioning.json"), "r", encoding="utf-8"
            ) as file:
                return RevisioningSchema().load(json.load(file))
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            return cls()

    def __init__(self, **kwargs):
        self.revisions = (
            kwargs["revisions"]
            if "revisions" in kwargs
            else [
                Revision(
                    major_version=conf.VERSION, number=0, version_tag=conf.VERSIONTAG
                )
            ]
        )
        self.current = (
            kwargs["current"]
            if "current" in kwargs
            else Revision(
                major_version=conf.VERSION, number=0, version_tag=conf.VERSIONTAG
            )
        )
        self.save()

    def revise(self, reset_num=False):
        if reset_num:
            rev = Revision(number=0)
        else:
            rev = Revision()
        self.revisions.append(rev)
        self.current = rev
        self.save()

    def calculate(self):
        if conf.VERSION != self.current.major_version:
            toLog = (
                "Major version is different: "
                + self.current.major_version
                + " =/= "
                + conf.VERSION
                + ". Resetting revision number..."
            )
            self.revise(reset_num=True)
            return toLog
        elif abs(self.current.lines - get_lines(conf.rootDir)) >= 3:
            dif = get_lines(conf.rootDir) - self.current.lines
            if dif > 0:
                verb = "added"
            else:
                verb = "removed"
            toLog = (
                "Revisioning line difference exceeded: "
                + "{:,}".format(int(abs(dif)))
                + " lines "
                + verb
                + " to codebase. Incrementing revision number..."
            )
            self.revise()
            return toLog
        elif self.current.hash != get_hash(conf.rootDir):
            toLog = (
                "Revisioning hash is different: ..."
                + self.current.hash[-8:]
                + " =/= ..."
                + get_hash(conf.rootDir)[-8:]
                + ". Incrementing revision number..."
            )
            self.revise()
            return toLog
        else:
            return "No revisions detected."

    def save(self):
        try:
            os.makedirs(conf.orm.botDir)
        except FileExistsError:
            pass
        with open(
            os.path.join(conf.orm.botDir, "revisioning.json"), "w", encoding="utf-8"
        ) as file:
            json.dump(
                RevisioningSchema().dump(self),
                file,
                sort_keys=True,
                indent=4,
                separators=(",", ": "),
            )
