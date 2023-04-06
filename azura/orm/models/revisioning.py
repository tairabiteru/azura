from core.conf import conf

import hashlib
import logging
import os
import tortoise


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


logger = logging.getLogger(conf.parent.name)


class Revision(tortoise.models.Model):
    hash = tortoise.fields.CharField(128)
    lines = tortoise.fields.IntField()
    characters = tortoise.fields.IntField()
    files = tortoise.fields.IntField()
    size = tortoise.fields.IntField()
    number = tortoise.fields.IntField()
    major_version = tortoise.fields.TextField()
    version_tag = tortoise.fields.TextField()
    timestamp = tortoise.fields.DatetimeField(auto_now_add=True)

    @property
    def version(self):
        return f"{self.major_version} R.{self.number} '{self.version_tag}'"

    @classmethod
    async def latest(cls):
        ordered = await cls.all().order_by("timestamp")
        try:
            return ordered.pop(-1)
        except IndexError:
            return await cls.revise("No revisions in database.", reset_revnum=True)

    @classmethod
    async def revise(cls, reason, reset_revnum=False):
        logger.warning(f"Creating new revision: {reason}")

        libfiles = []
        lines = 0
        chars = 0
        files = 0
        size = 0

        for subdir, dirs, fs in os.walk(os.path.join(os.getcwd(), "azura/")):
            for file in fs:
                files += 1
                size += os.path.getsize(os.path.join(subdir, file))

                if file.endswith(".py"):
                    fpath = os.path.join(subdir, file)
                    libfiles.append(fpath)
                    with open(fpath, "r") as fh:
                        for line in fh:
                            lines += 1
                            chars += len(line)

        hash = hashlib.sha512()
        for file in libfiles:
            hash.update(open(file, "rb").read())
        hash = hash.hexdigest()

        if reset_revnum is False:
            last = await cls.latest()
            number = last.number + 1
        else:
            number = 0

        current = await cls.create(
            hash=hash,
            lines=lines,
            characters=chars,
            files=files,
            size=size,
            number=number,
            major_version=conf.VERSION,
            version_tag=conf.VERSION_TAG
        )
        return current

    @classmethod
    async def calculate(cls):
        latest = await cls.latest()
        if conf.VERSION != latest.major_version:
            return await cls.revise(f"Major version is different: {latest.major_version} =/= {conf.VERSION}", reset_revnum=True)
        elif -3 >= (line_dif := (latest.lines - get_lines(os.path.join(os.getcwd(), "azura/")))) >= 3:
            verb = "added" if line_dif > 0 else "removed"
            return await cls.revise(f"{abs(line_dif)} lines {verb} to codebase.")
        elif latest.hash != (current_hash := get_hash(os.path.join(os.getcwd(), "azura/"))):
            return await cls.revise(f"Current hash {current_hash[-8:]} =/= latest hash {latest.hash[-8:]}.")
        else:
            logger.info("No revisions detected.")
            return latest
