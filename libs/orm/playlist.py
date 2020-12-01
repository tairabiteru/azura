from libs.core.conf import settings
from libs.ext.utils import strfdelta

from marshmallow import Schema, fields, pprint, post_load
import time
import datetime
import discord


class PlaylistEntrySchema(Schema):
    generator = fields.Str()
    custom_title = fields.Str()
    start = fields.Int()
    end = fields.Int()

    @post_load
    def make_obj(self, data, **kwargs):
        return PlaylistEntry(**data)


class PlaylistEntry:
    def __init__(self, **kwargs):
        self.generator = kwargs['generator']
        self.custom_title = kwargs['custom_title'] if 'custom_title' in kwargs else ""
        self.start = kwargs['start'] if 'start' in kwargs else 0
        self.end = kwargs['end'] if 'end' in kwargs else -1

    @property
    def start_timestamp(self):
        delta = datetime.timedelta(seconds=self.start)
        return strfdelta(delta, "{%H}:{%M}:{%S}")

    @property
    def end_timestamp(self):
        delta = datetime.timedelta(seconds=self.end)
        return strfdelta(delta, "{%H}:{%M}:{%S}")

    def embed(self, member):
        title = self.custom_title if self.custom_title else self.generator
        colour = discord.Colour(0x14ff)
        playlists = ", ".join(member.member_playlists(title))
        embed = discord.Embed(title=title, colour=colour)
        embed.add_field(name="Playlists", value=playlists)
        if self.custom_title:
            embed.add_field(name="Generator", value=self.generator)
        if self.start:
            embed.add_field(name="Start Time", value=self.start_timestamp)
        if self.end != -1:
            embed.add_field(name="End Time", value=self.end_timestamp)
        return embed
