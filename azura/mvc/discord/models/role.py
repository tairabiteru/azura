from django.db import models

from .base import DiscordBaseModel
from ..fields import RoleIDField


class Role(DiscordBaseModel):
    id = RoleIDField(primary_key=True, help_text="The Discord ID of this role.")
    guild = models.ForeignKey("discord.Guild", on_delete=models.CASCADE, help_text="The guild the role belongs to.")
    acl = models.ManyToManyField("discord.PermissionsObject", blank=True, help_text="The Access Control List determining permissions for users with this role.")
    description = models.CharField(max_length=512, default="No description provided.", help_text="The description of this role. Really only displayed in the tag roles interface.")

    @property
    def obj(self):
        try:
            if self._resolved['id'] is None:
                return None
            if isinstance(self._resolved['id'], Exception):
                raise self._resolved['id']
            return self._resolved['id']
        except KeyError:
            raise ValueError("resolve_all() must be called before accessing.")
        
    def __str__(self):
        try:
            return self.obj.name
        except ValueError:
            return f"RID ({self.id})"
    
    async def fetch_acl(self):
        acl = {}
        async for obj in self.acl.all():
            acl[obj.node] = obj.setting
        return acl