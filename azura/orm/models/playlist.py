import orm.models as models
import orm.fields as fields

import datetime
import hikari
import tortoise


def convert(timestamp):
    try:
        h, m, s = timestamp.split(':')
    except ValueError:
        m, s = timestamp.split(':')
        h = 0
    return int(h) * 3600 + int(m) * 60 + int(s)


class PlaylistEntry(models.HikariModel):
    source = tortoise.fields.TextField()
    title = tortoise.fields.TextField()
    start = tortoise.fields.IntField(default=0)
    end = tortoise.fields.IntField(default=-1)

    @property
    def start_timestamp(self):
        if self.start != 0:
            return str(datetime.timedelta(seconds=self.start))
        return ""
    
    @start_timestamp.setter
    def start_timestamp(self, timestamp):
        if timestamp == "":
            self.start = 0
        else:
            self.start = convert(timestamp)
    
    @property
    def end_timestamp(self):
        if self.end != -1:
            return str(datetime.timedelta(seconds=self.end))
        return ""
    
    @end_timestamp.setter
    def end_timestamp(self, timestamp):
        if timestamp == "":
            self.end = -1
        else:
            self.end = convert(timestamp)
    
    async def get_embed(self):
        name = self.title if self.title else "Untitled Entry"
        if self.source.startswith("http://") or self.source.startswith("https://"):
            embed = hikari.Embed(title=name, url=self.source)
        else:
            embed = hikari.Embed(title=name)
        
        start = "Track Beginning" if self.start == 0 else self.start
        end = "Track Ending" if self.end == -1 else self.end
        embed.add_field(name="Start", value=start, inline=True)
        embed.add_field(name="End", value=end, inline=True)
        return embed


class Playlist(models.HikariModel):
    owner = fields.UserField()
    name = tortoise.fields.CharField(max_length=256)
    description = tortoise.fields.TextField(default="No description provided.")
    is_public = tortoise.fields.BooleanField(default=False)
    items = tortoise.fields.ManyToManyField("models.PlaylistEntry")

    class Meta:
        unique_together = ("owner", "name")

    async def serialize(self):
        items = await self.items.all()
        data = {
                'id': self.id,
                'owner': self.owner.id,
                'name': self.name,
                'description': self.description,
                'is_public': self.is_public,
                'items': []
            }

        for item in items:
            data['items'].append(
                {
                    'id': item.id,
                    'source': item.source,
                    'title': item.title,
                    'start': item.start_timestamp,
                    'end': item.end_timestamp
                }
            )
        return data
    
    async def get_embed(self):
        items = await self.items.all()
        item_contents = ""
        if items:
            for i, item in enumerate(items):
                if item.title is not None:
                    item_contents += f"[0;32m{i+1}[0m. [0;34m{item.title}[0m\n"
                else:
                    item_contents += f"[0;32m{i+1}[0m. [0;34m{item.source}[0m\n"
        else:
            item_contents = "This playlist is empty."

        embed = hikari.Embed(title=self.name)
        embed.description = self.description
        embed.add_field(name="Public", value=self.is_public, inline=True)
        embed.add_field(name="Length", value=len(items), inline=True)
        embed.add_field(name="Entries", value=f"```ansi\n{item_contents}```")
        return embed
