from __future__ import annotations
from django.db import models
from sortedm2m.fields import SortedManyToManyField


from ...core.models import BaseAsyncModel
from .library import Song


class Playlist(BaseAsyncModel):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey("discord.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=256)
    description = models.TextField(default="No description provided.")
    songs = SortedManyToManyField(Song, blank=True)
    is_global = models.BooleanField(default=False)
    
    class Meta: # type: ignore
        unique_together = ('owner', 'name',)
    
    def __str__(self) -> str:
        return self.name