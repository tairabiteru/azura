from libs.core.conf import settings

import json
import os

from marshmallow import Schema, fields, pprint, post_load


class SongDataEntrySchema(Schema):
    vid = fields.Str()
    title = fields.Str()
    plays = fields.Dict(keys=fields.Int, values=fields.Int)

    @post_load
    def make_obj(self, data, **kwargs):
        return SongDataEntry(**data)

class SongDataEntry:
    def __init__(self, vid, **kwargs):
        self.vid = vid
        self.title = kwargs['title'] if 'title' in kwargs else ""
        self.plays = kwargs['plays'] if 'plays' in kwargs else {}

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
    data = fields.Dict(keys=fields.Str, values=fields.Nested(SongDataEntrySchema))

    @post_load
    def make_obj(self, data, **kwargs):
        return GlobalSongData(**data)

class GlobalSongData:
    @classmethod
    def obtain(cls, vid=None):
        try:
            with open(os.path.join(settings['orm']['botDirectory'], "global_song_data.json"), 'r', encoding='utf-8') as file:
                if not vid:
                    return GlobalSongDataSchema().load(json.load(file))
                else:
                    try:
                        return GlobalSongDataSchema().load(json.load(file)).data[vid]
                    except KeyError:
                        return SongDataEntry(vid)
        except FileNotFoundError:
            if vid:
                return SongDataEntry(vid)
            else:
                return cls()

    def __init__(self, **kwargs):
        self.data = kwargs['data'] if 'data' in kwargs else {}

    def updateSong(self, song):
        self.data[song.vid] = song
        self.save()

    def save(self):
        try:
            os.makedirs(settings['orm']['botDirectory'])
        except FileExistsError:
            pass
        with open(os.path.join(settings['orm']['botDirectory'], "global_song_data.json"), 'w', encoding='utf-8') as file:
            json.dump(GlobalSongDataSchema().dump(self), file, indent=4, separators=(',', ': '))
