from __future__ import annotations

import os
from uuid import uuid4

import music_tag
from django.core.exceptions import SynchronousOnlyOperation
from django.db import models
from django.dispatch import receiver
from jarowinkler import jarowinkler_similarity as jw_similarity

from ...core.models import BaseAsyncModel


def get_upload_path(instance: Song, filename: str) -> str:
    ext = filename.split(".")[-1]
    return f"cabinet/{instance.library.id}/{instance.name} [{uuid4().hex}].{ext}"


class Library(BaseAsyncModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=256)

    def __str__(self) -> str:
        return self.name


class Artist(BaseAsyncModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=256)

    def __str__(self) -> str:
        return self.name


class Song(BaseAsyncModel):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=256)
    file = models.FileField(upload_to=get_upload_path)
    library = models.ForeignKey("Library", on_delete=models.CASCADE)
    artists = models.ManyToManyField("Artist")

    def __str__(self) -> str:
        try:
            artists = []
            for artist in self.artists.all():
                artists.append(artist)
        except SynchronousOnlyOperation:
            return f"{self.id} - {self.name}"
        return f"{artists[0].name} - {self.name}"

    @property
    def title(self) -> str:
        return str(self)

    def compute_similarity(self, name: str) -> float:
        return jw_similarity(self.name, name)

    @classmethod
    async def search(cls, term: str) -> list[tuple[float, Song]]:
        songs = []
        async for song in cls.objects.all():
            if term.lower() in song.name.lower():
                songs.append((song.compute_similarity(term), song))
        return list(reversed(sorted(songs, key=lambda x: x[0])))


@receiver(models.signals.post_delete, sender=Song)
def auto_remove_deleted_song(sender, instance, **kwargs):
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)


@receiver(models.signals.post_save, sender=Song)
def auto_id3_update(sender, instance, **kwargs):
    if instance.file.path.endswith(".mp3"):
        f = music_tag.load_file(instance.file.path)
        f["title"] = instance.name
        f["artist"] = []

        for artist in instance.artists.all():
            f["artist"].append(artist.name)
        f.save()


class Stream(BaseAsyncModel):
    id = models.BigAutoField(primary_key=True)
    author = models.ForeignKey("discord.User", on_delete=models.CASCADE)
    uri = models.CharField(max_length=512)
    name = models.CharField(max_length=256)

    def __str__(self) -> str:
        return f"{self.name}@{self.uri}"
