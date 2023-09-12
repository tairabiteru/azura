from ..core.models import BaseAsyncModel
from ..discord.models import DiscordBaseModel, Channel
from django.db import models
from ...ext.utils import utcnow
from ...core.conf import Config
from ...core.conf import __VERSION__, __TAG__

conf = Config.load()

import aiofiles
import colorlog
import copy
import hashlib
import jinja2
import os
import sys


logger = colorlog.getLogger(conf.name)


class Child(BaseAsyncModel):
    name = models.CharField(unique=True, primary_key=True, max_length=32)
    token = models.CharField(max_length=128)
    ws_host = models.CharField(max_length=128)
    ws_port = models.IntegerField()
    log_color = models.CharField(max_length=64, default="light_green")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "children"

    def construct_config(self, base_conf):
        new_conf = copy.deepcopy(base_conf)
        new_conf.name = self.name
        new_conf.token = self.token
        new_conf.lavalink.websocket_host = self.ws_host
        new_conf.lavalink.websocket_port = self.ws_port
        new_conf.log_color = self.log_color
        return new_conf


class OperationalVariables(DiscordBaseModel):
    reinit_timestamp = models.DateTimeField(null=True, blank=True, default=None, help_text="The time when reinitialization took place.")
    reinit_channel = models.ForeignKey("discord.Channel", null=True, on_delete=models.SET_NULL, blank=True, default=None, help_text="The channel reinitialization was initiated in.")
    reinit_message = models.BigIntegerField(null=True, blank=True, default=None, help_text="The Discord ID of the message sent just before reinitialization.")

    class Meta:
        verbose_name_plural = "operational variables"
    
    @classmethod
    async def aget(cls):
        try:
            self = await cls.objects.aget(id=1)
        except cls.DoesNotExist:
            self = cls()
            await self.asave()
        return self
    
    @classmethod
    async def set_for_reinit(cls, channel=None, message=None):
        opvars = await cls.aget()
        if channel is not None:
            opvars.reinit_channel = await Channel.objects.aget(id=channel.id)
        if message is not None:
            opvars.reinit_message = message.id
        opvars.reinit_timestamp = utcnow()
        await opvars.asave()
    
    @classmethod
    async def clear_for_reinit(cls):
        opvars = await cls.aget()
        opvars.reinit_channel = None
        opvars.reinit_message = None
        opvars.reinit_timestamp = None
        await opvars.asave()


class Revision(BaseAsyncModel):
    CODE_EXTENSIONS = [
        ".py", ".html", ".js", ".css"
    ]

    EXCLUDE_FOLDERS = [
        ".venv", "migrations", "logs", "static/admin", "bin"
    ]

    hash = models.CharField(max_length=128, help_text="The SHA512 digest of the codebase.")
    lines = models.IntegerField(help_text="The number of code lines in the codebase.")
    chars = models.IntegerField(help_text="The number of code characters in the codebase.")
    files = models.IntegerField(help_text="The number of code files in the codebase.")
    size = models.IntegerField(help_text="The total size in bytes of the entire root directory.")
    number = models.IntegerField(help_text="The revision number.")
    version = models.CharField(max_length=64, help_text="The name of the major version.")
    tag = models.CharField(max_length=128, help_text="The version tag, appearing after the major version and revision number.")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="The time when this version was first entered into.")

    class Meta:
        get_latest_by = "timestamp"
    
    def __eq__(self, other):
        fields = ['version', 'lines', 'hash']
        for field in fields:
            if getattr(self, field) != getattr(other, field):
                return False
        else:
            return True
    
    def __str__(self):
        return f"{conf.name} {self.full_version}"

    @property
    def full_version(self):
        return f"{self.version} R.{self.number} '{self.tag}'"
    
    @classmethod
    async def recompute_current(cls):
        lines = 0
        chars = 0
        files = 0
        size = 0
        hash = hashlib.sha512()

        for subdir, dirs, fs in os.walk(os.path.join(conf.root)):
            if not any([f in subdir for f in cls.EXCLUDE_FOLDERS]):
                for file in fs:
                    files += 1
                    size += os.path.getsize(os.path.join(subdir, file))

                    if any([file.endswith(ext) for ext in cls.CODE_EXTENSIONS]):
                        async with aiofiles.open(os.path.join(subdir, file), "rb") as fh:
                            data = await fh.read()
                            hash.update(data)
                            chars += len(data)
                            data = list(reversed(data.split(b"\n")))
                            for i, line in enumerate(data):
                                if line == b"":
                                    data.pop(i)
                                else:
                                    break
                            lines += len(data)
        
        hash = hash.hexdigest()

        try:
            last = await cls.objects.alatest()
            if last.version != __VERSION__:
                number = 0
            else:
                number = last.number + 1
        except cls.DoesNotExist:
            number = 0
        
        current = cls(
            hash=hash,
            lines=lines,
            chars=chars,
            files=files,
            size=size,
            number=number,
            version=__VERSION__,
            tag=__TAG__
        )
        return current
    
    @classmethod
    async def calculate(cls):
        try:
            last = await cls.objects.alatest()
        except cls.DoesNotExist:
            logger.warning("No existing revisions in database. Recomputing.")
            current = await cls.recompute_current()
            await current.asave()
            return current
        
        apparent = await cls.recompute_current()
        if last != apparent:
            if last.version != apparent.version:
                logger.warning(f"Major version is different: {last.version} =/= {apparent.version}.")
            elif last.lines != apparent.lines:
                verb = "added" if apparent.lines > last.lines else "removed"
                plural = "line" if abs(apparent.lines - last.lines) == 1 else "lines"
                logger.warning(f"{abs(apparent.lines - last.lines)} {plural} {verb} to codebase.")
            elif last.hash != apparent.hash:
                logger.warning(f"Current hash {apparent.hash[-8:]} =/= last hash {last.hash[-8:]}.")
            await apparent.asave()
            return apparent
        else:
            logger.info("No changes detected in codebase.")
            return last


class FAQEntry(BaseAsyncModel):
    CTX = {
        'conf': conf,
        'python_version': f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    }

    title = models.CharField(max_length=256)
    text = models.TextField()

    class Meta:
        verbose_name = "FAQ Entry"
        verbose_name_plural = "FAQ Entries"

    def render(self, field):
        value = getattr(self, field)
        jinja = jinja2.Environment(loader=jinja2.BaseLoader)
        return jinja.from_string(value).render(self.ctx)

    @property
    def ctx(self):
        return FAQEntry.CTX

    def __str__(self):
        return self.render('title')

