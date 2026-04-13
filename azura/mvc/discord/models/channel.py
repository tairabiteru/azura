from django.db import models
from .base import DiscordBaseModel
from ..fields import ChannelIDField, ChannelTypeField


class Channel(DiscordBaseModel):
    id = ChannelIDField(primary_key=True, help_text="The channel's Discord ID.")
    type = ChannelTypeField(help_text="The type of channel this is.")
    guild = models.ForeignKey("discord.Guild", on_delete=models.CASCADE, related_name="channels_guild", help_text="The guild this channel belongs to.")

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
            return f"{self.obj.name}"
        except (ValueError, AttributeError): 
            return f"CID: {self.id}"