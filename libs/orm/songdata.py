from libs.core.conf import conf
from libs.ext.player.track import Track

import json
import os

from marshmallow import Schema, fields, post_load

class SongDataEntrySchema(Schema):
    vid = fields.Str(allow_none=True)
    title = fields.Str()
    author = fields.Str(allow_none=True)
    length = fields.Int()
    plays = fields.Dict(keys=fields.Int, values=fields.Int)

    @post_load
    def make_obj(self, data, **kwargs):
        return SongDataEntry(**data)

class SongDataEntry:
    def __init__(self, **kwargs):
        self.vid = kwargs['track'].ytid if 'track' in kwargs else kwargs['vid']
        self.title = kwargs['track'].title if 'track' in kwargs else kwargs['title']
        self.author = kwargs['track'].author if 'track' in kwargs else kwargs['author']
        self.length = kwargs['track'].length if 'track' in kwargs else kwargs['length']
        self.plays = kwargs['plays'] if 'plays' in kwargs else {}

    def __eq__(self, other):
        if isinstance(other, SongDataEntry):
            if other.vid and self.vid:
                return other.vid == self.vid
            title = other.title == self.title
            author = other.author == self.author
            length = other.length == self.length
            return (title and author and length)
        return False

    @property
    def global_plays(self):
        plays = 0
        for uid, individual_plays in self.plays.items():
            plays += individual_plays
        return plays

    def plays_by(self, uid=None):
        try:
            return self.plays[uid]
        except KeyError:
            return 0

    def increment_plays(self, uid):
        try:
            self.plays[uid] += 1
        except KeyError:
            self.plays[uid] = 1


class GlobalSongDataSchema(Schema):
    data = fields.List(fields.Nested(SongDataEntrySchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return GlobalSongData(**data)

class GlobalSongData:
    @classmethod
    def obtain(cls, entry=None):
        if isinstance(entry, Track):
            entry = SongDataEntry(track=entry)
        elif not isinstance(entry, SongDataEntry) and not isinstance(entry, type(None)):
            raise TypeError
        try:
            filename = os.path.join(conf.orm.botDir, "global_song_data.json")
            with open(filename, 'r', encoding='utf-8') as file:
                gsd = GlobalSongDataSchema().load(json.load(file))
                if not entry:
                    return gsd
                else:
                    for sde in gsd.data:
                        if entry == sde:
                            return sde
                    else:
                        return entry
        except FileNotFoundError:
            if not entry:
                return cls()
            return entry

    def __init__(self, **kwargs):
        self.data = kwargs['data'] if 'data' in kwargs else []

    def updateEntry(self, entry):
        if not isinstance(entry, SongDataEntry):
            raise TypeError
        new = []
        replaced = False
        for sde in self.data:
            if sde == entry:
                new.append(entry)
                replaced = True
            else:
                new.append(sde)
        if not replaced:
            new.append(entry)
        self.data = new
        self.save()

    def save(self):
        try:
            os.makedirs(conf.orm.botDir)
        except FileExistsError:
            pass
        with open(os.path.join(conf.orm.botDir, "global_song_data.json"), 'w', encoding='utf-8') as file:
            json.dump(GlobalSongDataSchema().dump(self), file, indent=4, separators=(',', ': '))
