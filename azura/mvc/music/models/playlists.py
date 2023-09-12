from ...core.models import BaseAsyncModel
from django.db import models

import hikari
import re


class PlaylistEntry(BaseAsyncModel):
    playlist = models.ForeignKey("music.Playlist", on_delete=models.CASCADE, related_name="entries")
    source = models.TextField()
    title = models.TextField()
    start = models.CharField(max_length=16, default='')
    end = models.CharField(max_length=16, default='')
    index = models.IntegerField()
    failed = models.BooleanField(default=False)
   
    class Meta:
        unique_together = (('index', 'playlist'), ('title', 'playlist'))

    @property
    def start_ms(self):
        if self.start == '':
            return 0
        return self.td_str_to_ms(self.start)
    
    @property
    def end_ms(self):
        if self.end == '':
            return None
        return self.td_str_to_ms(self.end)
        
    def __str__(self):
        return f"{self.playlist.name} - {self.title}"

    @staticmethod
    def validate_timedelta(delta: str) -> str:
        if delta is None:
            return ""

        if re.fullmatch("\d+:\d\d:\d\d", delta):
            return delta
        elif re.fullmatch("\d+:\d\d", delta):
            return delta
        raise ValueError(f"Invalid format `{delta}`. It must be either `00:00` or `00:00:00`.")

    @staticmethod
    def td_str_to_ms(delta: str) -> int:
        delta = delta.split(":")
        if len(delta) == 3:
            h, m, s = tuple(delta)
        else:
            delta.insert(0, "0")
            h, m, s = tuple(delta)
        h, m, s = int(h), int(m), int(s)
        h *= 3600000
        m *= 60000
        s *= 1000
        return sum([h, m, s])

    async def get_embed(self):
        embed = hikari.Embed(title=self.title)
        if self.source.startswith("https://") or self.source.startswith("http://"):
            embed.url = self.source
        
        start = "Beginning of track" if not self.start else self.start
        end = "End of track" if not self.end else self.end
        embed.add_field(name="Start", value=start, inline=True)
        embed.add_field(name="End", value=end, inline=True)
        embed.add_field(name="Track Number", value=f"#{self.index+1}")
        return embed



class Playlist(BaseAsyncModel):
    owner = models.ForeignKey("discord.User", on_delete=models.CASCADE, related_name="playlists")
    name = models.CharField(max_length=256)
    description = models.TextField(default="No description provided.")
    is_public = models.BooleanField(default=False)

    class Meta:
        unique_together = ('owner', 'name')

    def __str__(self):
        try:
            return f"{self.owner.obj.username} - {self.name}"
        except ValueError:
            return f"{self.owner.id} - {self.name}"
    
    async def get_entries(self):
        entries = []
        async for entry in PlaylistEntry.objects.filter(playlist=self):
            entries.append(entry)
        return sorted(entries, key=lambda x: x.index)

    async def get_embed(self):
        entries = await self.get_entries()
        if not entries:
            contents = "This playlist is empty."
        else:
            contents = ""
            for i, entry in enumerate(entries):
                contents += f"{i+1}. {entry.title}"
        
        embed = hikari.Embed(
            title=self.name,
            description=self.description
        )
        embed.add_field(name="Public", value=self.is_public, inline=True)
        embed.add_field(name="Length", value=len(entries), inline=True)
        embed.add_field(name="Entries", value=f"```{contents}```")
        return embed

    async def get_next_index(self):
        entries = await self.get_entries()
        return len(entries)

    async def serialize(self):
        entries = await self.get_entries()
        for i in range(0, len(entries)):
            entries[i] = {
                'source': entries[i].source,
                'title': entries[i].title,
                'start': entries[i].start,
                'end': entries[i].end
            }

        return {
            'id': self.id,
            'owner': self.owner.id,
            'name': self.name,
            'description': self.description,
            'is_public': self.is_public,
            'entries': entries
        }