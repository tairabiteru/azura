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


class MemberSchema(Schema):
    uid = fields.Int(required=True)
    name = fields.Str()
    acl = fields.Dict()
    playlist_names = fields.List(fields.Str)
    playlist_entries = fields.Dict(keys=fields.Str, values=fields.Nested(PlaylistEntrySchema))
    selected = fields.Str()
    history = fields.List(fields.Str)
    last_volume = fields.Float()
    volume_step = fields.Float()

    @post_load
    def make_obj(self, data, **kwargs):
        return Member(**data)


class Member:
    @classmethod
    def obtain(cls, uid):
        try:
            with open(os.path.join(settings['orm']['memberDirectory'], str(uid) + "_" + cls.__name__ + ".json"), 'r', encoding='utf-8') as file:
                return MemberSchema().load(json.load(file))
        except FileNotFoundError:
            return cls(uid)

    def __init__(self, uid, **kwargs):
        self.uid = uid
        self.name = kwargs['name'] if 'name' in kwargs else "unknown"
        self.acl = kwargs['acl'] if 'acl' in kwargs else {}
        self.playlist_names = kwargs['playlist_names'] if 'playlist_names' in kwargs else []
        self.playlist_entries = kwargs['playlist_entries'] if 'playlist_entries' in kwargs else {}
        self.selected = kwargs['selected'] if 'selected' in kwargs else ""
        self.history = kwargs['history'] if 'history' in kwargs else []
        self.last_volume = kwargs['last_volume'] if 'last_volume' in kwargs else 0.5
        self.volume_step = kwargs['volume_step'] if 'volume_step' in kwargs else 0.05

    @property
    def lower_playlist_names(self):
        return list([name.lower() for name in self.playlist_names])

    def update_history(self, history_entry):
        self.history.append(history_entry)
        if len(self.history) > 5000:
            self.history.pop(0)
        self.save()

    def increment_playback(self, vid, title):
        history_entry = vid + " :=: " + title
        self.update_history(history_entry)
        song = GlobalSongData.obtain(vid=vid)
        global_data = GlobalSongData.obtain()
        if not song.title:
            song.title = title
        song.increment_plays(self.uid)
        global_data.updateSong(song)

    def get_plays(self, vid=None):
        return GlobalSongData.obtain(vid=vid).plays_by(uid=self.uid)

    def add_playlist(self, name):
        if name.lower() in list([playlist_name.lower() for playlist_name in self.playlist_names]):
            raise PlaylistExistsError("'" + name + "' is already an entry in this user's playlists.")
        self.playlist_names.append(name)
        self.save()

    def delete_playlist(self, name):
        if name.lower() not in list([playlist_name.lower() for playlist_name in self.playlist_names]):
            raise PlaylistNotFoundError("A playlist with the name '" + name + "' does not exist.")
        for playlist in self.playlist_names:
            if playlist.lower() == name.lower():
                self.playlist_names.remove(playlist)
                for vid, entry in self.playlist_entries.items():
                    if playlist.lower() in entry.playlists:
                        print(entry.playlists)
                        entry.playlists.remove(playlist)
                        self.playlist_entries[vid] = entry
        self.save()

    def add_playlist_entry(self, playlist_entry):
        try:
            existing_entry = self.playlist_entries[playlist_entry.vid]
            if any([playlist in existing_entry.playlists for playlist in playlist_entry.playlists]):
                raise DuplicatePlaylistError("One or more of the playlists being added already exist in the entry.")
            if any([playlist not in self.playlist_names for playlist in playlist_entry.playlists]):
                raise PlaylistNotFoundError("One or more of the playlists being added do not exist in this user's playlists.")
            existing_entry.playlists += playlist_entry.playlists
            self.playlist_entries[existing_entry.vid] = existing_entry
        except KeyError:
            self.playlist_entries[playlist_entry.vid] = playlist_entry
        self.save()

    def vid_exists(self, vid):
        return any([entry.vid == vid for videoid, entry in self.playlist_entries.items()])

    def remove_playlist_from_entry(self, playlist_entry):
        for playlist in playlist_entry.playlists:
            self.playlist_entries[playlist_entry.vid].playlists.remove(playlist)
        if len(self.playlist_entries[playlist_entry.vid].playlists) == 0:
            self.delete_playlist_entry(playlist_entry)
            self.save()
            return True
        self.save()
        return False

    def delete_playlist_entry(self, title_or_generator):
        found = False
        for videoid, entry in self.playlist_entries.items():
            if entry.generator == title_or_generator:
                entry = self.playlist_entries.pop(entry.vid)
                self.save()
                return entry
        for videoid, entry in self.playlist_entries.items():
            if entry.custom_title.lower() == title_or_generator.lower():
                entry = self.playlist_entries.pop(entry.vid)
                self.save()
                return entry
        raise PlaylistEntryNotFoundError

    def entries_in_playlist(self, name):
        if name.lower() not in list([playlist_name.lower() for playlist_name in self.playlist_names]):
            raise PlaylistNotFoundError
        entries = []
        for vid, entry in self.playlist_entries.items():
            if name.lower() in list([playlist_name.lower() for playlist_name in entry.playlists]):
                entries.append(entry)
        return entries

    def get_proper_playlist_name(self, name):
        for playlist_name in self.playlist_names:
            if name.lower() == playlist_name.lower():
                return playlist_name

    def save(self):
        try:
            os.makedirs(settings['orm']['memberDirectory'])
        except FileExistsError:
            pass
        with open(os.path.join(settings['orm']['memberDirectory'], str(self.uid) + "_" + self.__class__.__name__ + ".json"), 'w', encoding='utf-8') as file:
            json.dump(MemberSchema().dump(self), file, indent=4, separators=(',', ': '))
