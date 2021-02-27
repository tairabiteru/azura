from libs.core.conf import conf
from libs.orm.playlist import PlaylistEntrySchema
from libs.orm.songdata import GlobalSongData

import json
from marshmallow import Schema, fields, post_load
import os
import discord
import wavelink


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


class EqualizerSchema(Schema):
    levels = fields.Dict(keys=fields.Str, values=fields.Float)
    name = fields.Str()
    description = fields.Str()

    @post_load
    def make_obj(self, data, **kwargs):
        return Equalizer(**data)

class Equalizer:
    DEFAULTS = {
        '50 Hz': 0.0,
        '100 Hz': 0.0,
        '156 Hz': 0.0,
        '220 Hz': 0.0,
        '311 Hz': 0.0,
        '440 Hz': 0.0,
        '622 Hz': 0.0,
        '880 Hz': 0.0,
        '1.25 KHz': 0.0,
        '1.75 KHz': 0.0,
        '2.5 KHz': 0.0,
        '3.5 KHz': 0.0,
        '5 KHz': 0.0,
        '10 KHz': 0.0,
        '20 KHz': 0.0
    }

    @classmethod
    def buildFromEq(cls, eq):
        desc = {
            'Boost': 'Emphasizes punchy bass and crisp mid to high tones. Not suitable for tracks with deep, low bass.',
            'Flat': 'The default equalizer.',
            'Metal': 'Equalizer for metal and rock. May cause clipping on bassy songs.',
            'Piano': 'Good for piano tracks, or tracks which emphasize female vocals. Can also be used as a bass cutoff.'
        }
        levels = {}

        if eq.name == "Piano":
            eq.raw.append((14, 0.0))

        for i, band in enumerate(Equalizer.DEFAULTS):
            levels[band] = eq.raw[i][1]
        return cls(name=eq.name, description=desc[eq.name], levels=levels)

    def __init__(self, **kwargs):
        self.name = kwargs['name'] if 'name' in kwargs else 'Custom Settings'
        self.description = kwargs['description'] if 'description' in kwargs else 'No description provided.'
        self.levels = kwargs['levels'] if 'levels' in kwargs else Equalizer.DEFAULTS

    @classmethod
    def buildFromJSON(cls, data):
        levels = {}
        for band, level in data['levels'].items():
            levels[band] = float(level)
        return cls(name=data['name'], description=data['description'], levels=levels)

    @property
    def wavelinkEQ(self):
        bands = []
        for i, band in enumerate(self.levels):
            bands.append((i, self.levels[band]))
        return wavelink.Equalizer(levels=bands)


class SettingsSchema(Schema):
    volumeStep = fields.Int()
    promptOnSearch = fields.Boolean()
    useEqualizer = fields.Boolean()
    eqOverride = fields.Boolean()

    @post_load
    def make_obj(self, data, **kwargs):
        return Settings(**data)

class Settings:
    def __init__(self, **kwargs):
        self.volumeStep = kwargs['volumeStep'] if 'volumeStep' in kwargs else 5
        self.promptOnSearch = kwargs['promptOnSearch'] if 'promptOnSearch' in kwargs else True
        self.useEqualizer = kwargs['useEqualizer'] if 'useEqualizer' in kwargs else True
        self.eqOverride = kwargs['eqOverride'] if 'eqOverride' in kwargs else False

        self._descriptions = {
            'volumeStep': "Controls the rate at which volume is changed when using buttons. For example, if volumeStep = 5, then each time the volume up button is pressed, the volume will increase by 5%.",
            'promptOnSearch': "Controls whether or not you are prompted when you enqueue songs with a search. If enabled you will be asked to select from the top 5 results when a song is enqueued with a search. If disabled, the first result will be automatically selected each time.",
            'useEqualizer': "Controls whether or not the equalizer is enabled. If enabled, the equalizer set on this page will be used. If disabled, the normal internal equalizer will be used. Equalization can be used to fine tune audio for excellent sound, but it can also mess it up if one does not know what they're doing.",
            'eqOverride': "Controls whether or not the equalizer setting on this page overrides any equalizers for songs in a playlist. If enabled, the equalizer set here will always be used, regardless of any per-song specifications in a playlist."
        }

        self._numRangeValues = {
            'volumeStep': [1, 50]
        }

    @property
    def _allSettings(self):
        settings = []
        for attr in dir(self):
            if not attr.startswith("_"):
                settings.append(attr)
        return sorted(settings)


class MemberSchema(Schema):
    uid = fields.Int(required=True)
    name = fields.Str()
    acl = fields.Dict()
    playlists = fields.Dict(keys=fields.Str, values=fields.List(fields.Nested(PlaylistEntrySchema)))
    selected = fields.Str()
    history = fields.List(fields.Str)
    last_volume = fields.Int()
    settings = fields.Nested(SettingsSchema)
    equalizers = fields.List(fields.Nested(EqualizerSchema))
    current_eq = fields.Str()

    @post_load
    def make_obj(self, data, **kwargs):
        return Member(**data)

class Member:
    @classmethod
    def obtain(cls, uid):
        try:
            filename = os.path.join(conf.orm.memberDir, f"{uid}_{cls.__name__}.json")
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
        self.settings = kwargs['settings'] if 'settings' in kwargs else Settings()

        if 'equalizers' in kwargs:
            self.equalizers = kwargs['equalizers']
        else:
            self.equalizers = []
            wavelinkEqs = [wavelink.Equalizer.boost, wavelink.Equalizer.flat, wavelink.Equalizer.metal, wavelink.Equalizer.piano]
            for eq in wavelinkEqs:
                eq = Equalizer.buildFromEq(eq())
                self.equalizers.append(eq)

        self.current_eq = kwargs['current_eq'] if 'current_eq' in kwargs else 'Flat'

    @property
    def currentEq(self):
        if not self.settings.useEqualizer:
            eqname = 'Flat'
        else:
            eqname = self.current_eq

        for eq in self.equalizers:
            if eq.name == eqname:
                return eq

    def getEq(self, name):
        for eq in self.equalizers:
            if eq.name == name:
                return eq
        else:
            return None

    def settingInRange(self, setting, value):
        values = self.settings._numRangeValues
        value = int(value)
        try:
            return (values[setting][0] <= value <= values[setting][1], values[setting])
        except KeyError:
            return (True, "any")

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
        while len(self.history) + 1 > conf.music.maxHistoryRecords:
            self.history.pop(0)
        self.history.append(track.title)
        gsd = GlobalSongData.obtain()
        sde = GlobalSongData.obtain(entry=track)
        sde.increment_plays(self.uid)
        gsd.updateEntry(sde)

        self.save()

    def save(self):
        try:
            os.makedirs(conf.orm.memberDir)
        except FileExistsError:
            pass
        filename = os.path.join(conf.orm.memberDir, f"{self.uid}_{self.__class__.__name__}.json")
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(MemberSchema().dump(self), file, indent=4, separators=(',', ': '))


class Playlist:
    def __init__(self):
        pass

    @classmethod
    async def convert(cls, ctx, argument):
        member = Member.obtain(ctx.author.id)
        return member.get_playlist(argument)[1]
