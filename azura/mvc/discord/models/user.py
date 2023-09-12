from django.db import models

from .base import DiscordBaseModel
from ..fields import UserIDField
from ...music.models import Playlist


class User(DiscordBaseModel):
    id = UserIDField(primary_key=True, help_text="The Discord ID of this user.")
    acl = models.ManyToManyField("discord.PermissionsObject", blank=True, help_text="The Access Control List of this user, determining their permissions.")
    locale_settings = models.OneToOneField("discord.Locale", on_delete=models.PROTECT, null=True, default=None)
    administrative_notes = models.TextField(blank=True, null=True)

    volume = models.IntegerField(default=100)
    volume_step = models.IntegerField(default=5)
    prompt_on_search = models.BooleanField(default=True)
    selected_playlist = models.ForeignKey("music.Playlist", on_delete=models.SET_NULL, null=True, blank=True, default=None)

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
    
    def save(self, *args, **kwargs):
        from .locale import Locale
        o2o_fields = {
            'locale_settings': Locale
        }
        for field, cls in o2o_fields.items():
            if getattr(self, field) is None:
                o = cls()
                o.save()
                setattr(self, field, o)
        return super().save(*args, **kwargs)
    
    async def asave(self, *args, **kwargs):
        from .locale import Locale
    
        o2o_fields = {
            'locale_settings': Locale
        }

        for field, cls in o2o_fields.items():
            try:
                s = await User.objects.select_related(field).aget(id=self.id)
                if getattr(s, field) is None:
                    o = cls()
                    await o.asave()
                    setattr(self, field, o)
            except User.DoesNotExist:
                o = cls()
                await o.asave()
                setattr(self, field, o)
        return await super().asave(*args, **kwargs)
    
    def __str__(self):
        try:
            return f"{self.obj.username}#{self.obj.discriminator}"
        except ValueError: 
            return f"UID: {self.id}"
        except AttributeError:
            return f"UID: {self.id} (Not in cache)"
    
    async def fetch_acl(self):
        acl = {}
        async for obj in self.acl.all():
            acl[obj.node] = obj.setting
        return acl
    
    async def localnow(self):
        locale = (await User.objects.select_related("locale_settings").aget(id=self.id)).locale_settings
        return locale.localnow()
    
    @property
    def locale(self):
        return self.locale_settings

    async def get_playlists(self):
        playlists = []
        async for playlist in Playlist.objects.filter(owner=self):
            playlists.append(playlist)
        return sorted(playlists, key=lambda x: x.name)