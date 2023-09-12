from ...core.models import BaseAsyncModel
from django.db import models


class PlaybackHistoryEntry(BaseAsyncModel):
    requester = models.ForeignKey("discord.User", on_delete=models.CASCADE)
    bot = models.CharField(max_length=32)
    track_title = models.TextField()
    track_source = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.track_title

    @classmethod
    async def get_embed(cls):
        # Todo write this
        pass

