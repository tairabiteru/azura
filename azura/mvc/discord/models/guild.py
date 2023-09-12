import zoneinfo

from .base import DiscordBaseModel
from ..fields import GuildIDField
from ...core.fields import TimezoneField
from .user import User
from ....ext.utils import utcnow


class Guild(DiscordBaseModel):
    id = GuildIDField(primary_key=True, help_text="The Discord ID of this guild.")
    timezone = TimezoneField(help_text="The timezone in which this guild operates.")

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
            return f"GID ({self.id})"
        
    def localnow(self):
        return utcnow().astimezone(zoneinfo.ZoneInfo(self.timezone))

    def save(self, *args, **kwargs):
        o2o_fields = {
        }
        for field, cls in o2o_fields.items():
            if getattr(self, field) is None:
                o = cls()
                o.save()
                setattr(self, field, o)
        return super().save(*args, **kwargs)
    
    async def asave(self, *args, **kwargs):
    
        o2o_fields = {
    
        }

        for field, cls in o2o_fields.items():
            try:
                s = await Guild.objects.select_related(field).aget(id=self.id)
                if getattr(s, field) is None:
                    o = cls()
                    await o.asave()
                    setattr(self, field, o)
            except Guild.DoesNotExist:
                o = cls()
                await o.asave()
                setattr(self, field, o)
        return await super().asave(*args, **kwargs)

    async def get_members(self, bot=None):
        if bot is not None:
            self.attach_bot(bot)
        await self.aresolve_all()
        
        for uid in self.obj.get_members():
            user, _ = await User.objects.aget_or_create(id=int(uid))
            yield user