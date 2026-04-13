import zoneinfo

from .base import DiscordBaseModel
from ..fields import GuildIDField
from ...core.fields import TimezoneField
from .user import User
from azura.lib.utils import utcnow


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

    async def get_members(self, bot=None):
        if bot is not None:
            self.attach_bot(bot)
        await self.aresolve_all()
        
        for uid in self.obj.get_members():
            user, _ = await User.objects.aget_or_create(id=int(uid))
            yield user