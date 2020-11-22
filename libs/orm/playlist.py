from libs.core.conf import settings

from marshmallow import Schema, fields, pprint, post_load


class PlaylistExistsError(Exception):
    """Raised when a playlist to be added already exists."""
    pass

class DuplicatePlaylistError(Exception):
    """Raised when an entry has a playlist added to it that it is already apart of."""
    pass

class PlaylistNotFoundError(Exception):
    """Raised when a playlist is added to an entry that does not exist."""
    pass

class PlaylistEntryNotFoundError(Exception):
    """Raised when a playlist entry cannot be found."""
    pass



class PlaylistEntrySchema(Schema):
    generator = fields.Str()
    vid = fields.Str()
    custom_title = fields.Str()
    start_time = fields.Int()
    end_time = fields.Int()
    playlists = fields.List(fields.Str)

    @post_load
    def make_obj(self, data, **kwargs):
        return PlaylistEntry(**data)

class PlaylistEntry:

    def __init__(self, **kwargs):
        self.generator = kwargs['generator'] if 'generator' in kwargs else ""
        self.vid = kwargs['vid'] if 'vid' in kwargs else ""
        self.custom_title = kwargs['custom_title'] if 'custom_title' in kwargs else ""
        self.start_time = kwargs['start_time'] if 'start_time' in kwargs else 0
        self.end_time = kwargs['end_time'] if 'end_time' in kwargs else -1
        self.playlists = kwargs['playlists'] if 'playlists' in kwargs else []

    @property
    def name(self):
        if self.custom_title:
            return self.custom_title
        else:
            return self.generator
