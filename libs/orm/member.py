from libs.core.conf import settings
from libs.ext.utils import localnow
from libs.ext.utils import render_load_bar
from libs.orm.playlist import PlaylistEntrySchema
from libs.orm.songdata import GlobalSongData

import datetime
import json
from marshmallow import Schema, fields, post_load
import math
import os
import random
import discord


class PlaylistExists(Exception):
    """Raised when a playlist to be added already exists."""
    pass

class PlaylistNotFound(Exception):
    """Raised when a playlist is expected to exist, but doesn't."""

class EntryNotFound(Exception):
    """Raised when an entry is expected to exist, but doesn't."""
    pass

class EntryExists(Exception):
    """Raised when an entry is added to a playlist which already contains it."""
    pass


class MemberSchema(Schema):
    uid = fields.Int(required=True)
    name = fields.Str()
    acl = fields.Dict()
    playlists = fields.Dict(keys=fields.Str, values=fields.List(fields.Nested(PlaylistEntrySchema)))
    selected = fields.Str()
    history = fields.List(fields.Str)
    last_volume = fields.Int()
    volume_step = fields.Int()

    @post_load
    def make_obj(self, data, **kwargs):
        return Member(**data)

class Member:
    @classmethod
    def obtain(cls, uid):
        try:
            filename = os.path.join(settings['orm']['memberDirectory'], f"{uid}_{cls.__name__}.json")
            with open(filename, 'r', encoding='utf-8') as file:
                out = MemberSchema().load(json.load(file))
                return out
        except FileNotFoundError:
            return cls(uid=uid)

    def __init__(self, **kwargs):
        self.uid = kwargs['uid']
        self.name = kwargs['name'] if 'name' in kwargs else "unknown"
        self.acl = kwargs['acl'] if 'acl' in kwargs else {}
        self.playlists = kwargs['playlists'] if 'playlists' in kwargs else {}
        self.selected = kwargs['selected'] if 'selected' in kwargs else ""
        self.history = kwargs['history'] if 'history' in kwargs else []
        self.last_volume = kwargs['last_volume'] if 'last_volume' in kwargs else 50
        self.volume_step = kwargs['volume_step'] if 'volume_step' in kwargs else 5

    def playlist_exists(self, name):
        for playlist in self.playlists:
            if playlist.lower() == name.lower():
                return playlist
        return None

    def add_playlist(self, name):
        if self.playlist_exists(name):
            raise PlaylistExists
        self.playlists[name] = []
        self.save()

    def del_playlist(self, name):
        playlist = self.playlist_exists(name)
        if playlist:
            del self.playlists[playlist]
            if playlist == self.selected:
                self.selected = ""
            self.save()
        else:
            raise PlaylistNotFound

    def playlist_embed(self, name=None):
        colour = discord.Colour(0x14ff)
        # If no playlists have been defined.
        if len(self.playlists) == 0:
            title = "__No Playlists__"
            desc = "You have not yet created any playlists."
            return discord.Embed(title=title, colour=colour, description=desc)

        # If we want a list of playlists.
        if not name:
            title = "__All Playlists__"
            desc = ""
            for playlist in self.playlists:
                if playlist.lower() == self.selected.lower():
                    desc += f"🠊 {playlist}\n"
                else:
                    desc += f"• {playlist}\n"
            desc = f"```CSS\n{desc}```"
            return discord.Embed(title=title, colour=colour, description=desc)

        # If no such playlist exists.
        name = self.playlist_exists(name)
        if not name:
            raise PlaylistNotFound

        title = f"__{name}__"
        if len(self.playlists[name]) == 0:
            desc = "This playlist is empty."
            return discord.Embed(title=title, colour=colour, description=desc)

        # Otherwise, the playlist exists, and has songs in it.
        desc = ""
        for i, entry in enumerate(self.playlists[name]):
            desc += f"{i+1}. "
            if entry.custom_title:
                desc += f"{entry.custom_title}\n"
            else:
                desc += f"{entry.generator}\n"
        desc = f"```CSS\n{desc}```"
        return discord.Embed(title=title, colour=colour, description=desc)

    def get_playlist(self, name):
        for playlist, entries in self.playlists.items():
            if playlist.lower() == name.lower():
                return (playlist, entries)
        else:
            raise PlaylistNotFound

    def add_playlist_entry(self, playlist, entry):
        playlist = self.playlist_exists(playlist)
        if not playlist:
            raise PlaylistNotFound
        if entry.custom_title:
            if any([entry.custom_title == e.custom_title for e in self.playlists[playlist]]):
                raise EntryExists
        if any([entry.generator == e.generator for e in self.playlists[playlist]]):
            raise EntryExists
        self.playlists[playlist].append(entry)
        self.save()

    def delete_playlist_entry(self, playlist, identifier):
        if not self.playlist_exists(playlist):
            raise PlaylistNotFound
        new = []
        removed = None
        for entry in self.playlists[playlist]:
            if entry.custom_title and identifier == entry.custom_title:
                removed = entry
            elif identifier == entry.generator:
                removed = entry
            else:
                new.append(entry)
        if not removed:
            raise EntryNotFound
        self.playlists[playlist] = new
        self.save()
        return removed

    def delete_from_all(self, identifier):
        removed = []
        for playlist in self.playlists:
            try:
                r = self.delete_playlist_entry(playlist, identifier)
                removed.append(r)
            except EntryNotFound:
                pass
        if not removed:
            raise EntryNotFound
        return removed

    def member_playlists(self, identifier):
        playlists = []
        for playlist, entries in self.playlists.items():
            for entry in entries:
                if identifier == entry.custom_title and playlist not in playlists:
                    playlists.append(playlist)
                elif identifier == entry.generator and playlist not in playlists:
                    playlists.append(playlist)
        return playlists

    def update_history(self, track):
        while len(self.history) + 1 > settings['orm']['maxHistoryRecords']:
            self.history.pop(0)
        self.history.append(track.title)
        gsd = GlobalSongData.obtain()
        sde = GlobalSongData.obtain(entry=track)
        sde.increment_plays(self.uid)
        gsd.updateEntry(sde)

        self.save()

    def save(self):
        try:
            os.makedirs(settings['orm']['memberDirectory'])
        except FileExistsError:
            pass
        filename = os.path.join(settings['orm']['memberDirectory'], f"{self.uid}_{self.__class__.__name__}.json")
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(MemberSchema().dump(self), file, indent=4, separators=(',', ': '))
