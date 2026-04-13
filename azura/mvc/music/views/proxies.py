import datetime
import koe

from ..models import Artist, Song
from ....lib.utils import strfdelta


class TrackProxy:
    def __init__(self, track: koe.Track):
        self._track = track
        self._song: Song | None = None
        self._artists: list[Artist] | None = None
        self._pos: str | None = None
    
    async def fetch(self) -> None:
        fname = self._track.info.identifier.split("/")[-1]
        self._song = await Song.objects.aget(file__contains=fname)
        
        self._artists = []
        async for artist in self._song.artists.all():
            self._artists.append(artist)
            
    def set_pos(self, pos: str) -> None:
        self._pos = pos
    
    @property
    def length(self) -> str:
        if self._track is None:
            raise RuntimeError
        return strfdelta(
            datetime.timedelta(milliseconds=self._track.info.length),
            '{%M}:{%S}'
        )
    
    @property
    def title(self) -> str:
        if self._track is None:
            raise RuntimeError
        return self._track.info.title
    
    @property
    def artists(self) -> str:
        if self._artists is None:
            raise RuntimeError
        return ", ".join([a.name for a in self._artists])
    
    @property
    def position(self) -> str:
        if self._pos is not None:
            return self._pos
        return ""


class CurrentTrackProxy(TrackProxy):
    def __init__(self, session: koe.Session | None):
        self._session = session
        
        if self._session is not None and self._session._current_track is not None:
            super().__init__(self._session._current_track)
        else:
            self._track = None
        
    async def fetch(self) -> None:
        if self._session and self._session._current_track is not None:
            await super().fetch()
    
    @property
    def position(self) -> str:
        if self._session and self._session._current_track_pos is not None:
            return strfdelta(
                datetime.timedelta(milliseconds=self._session._current_track_pos),
                '{%M}:{%S}'
            )
        return " - "
    
    @property
    def permyriad_done(self) -> int:
        if self._session and self._session._current_track is not None and self._session._current_track_pos is not None:
            pct = self._session._current_track_pos / self._session._current_track.info.length * 10000
            return int(round(pct, 0))
        return 0
    
    @property
    def title(self) -> str:
        try:
            return super().title
        except RuntimeError:
            return " - "
    
    @property
    def artists(self) -> str:
        try:
            return super().artists
        except AttributeError:
            return " - "
    
    @property
    def length(self) -> str:
        try:
            return super().length
        except RuntimeError:
            return " - "


class QueueProxy:
    def __init__(self, session: koe.Session | None):
        self._session = session
        
        if self._session is not None:
            self._queue = self._session.queue
        else:
            self._queue = None
            
        self._current_tracks: list[TrackProxy] | None = None
        self._pos: str | None = None
    
    async def fetch(self) -> None:
        if self._queue is not None:
            current_tracks, pos = await self._queue.get_all_and_pos()
            self._pos = str(pos+1)
            self._current_tracks = []
            
            for i, track in enumerate(current_tracks):
                track = TrackProxy(track)
                track.set_pos(str(i+1))
                await track.fetch()
                self._current_tracks.append(track)
    
    @property
    def current_tracks(self) -> list[TrackProxy]:
        if self._current_tracks is None:
            return []
        return self._current_tracks
    
    @property
    def position(self) -> str:
        if self._pos is None:
            return ""
        return self._pos


class SessionProxy:
    def __init__(self, session: koe.Session | None):
        self._session = session
        self.current_track = CurrentTrackProxy(session)
        self.queue = QueueProxy(self._session)
        
    async def fetch(self) -> None:
        await self.current_track.fetch()
        await self.queue.fetch()
    
    @property
    def volume(self) -> int:
        if self._session and self._session._volume is not None:
            return self._session._volume
        return 0
    
    @property
    def paused(self) -> bool:
        if self._session and self._session._paused is not None:
            return self._session._paused
        return False
    
    @property
    def repeat_mode(self) -> str:
        if self._session is None:
            return "repeat"
        
        if self._session._repeat_mode is koe.RepeatMode.NONE:
            return "repeat"
        elif self._session._repeat_mode is koe.RepeatMode.ALL:
            return "repeat_on"
        else:
            return "repeat_one_on"
    
    @property
    def channel_name(self) -> str:
        if not self._session:
            return "Not connected"
        
        voice = self._session.bot.cache.get_guild_channel(self._session.voice_id)
        assert voice is not None
        assert voice.name is not None
        return voice.name


class SongProxy:
    def __init__(self, song: Song):
        self._song = song
        self._artists = []
    
    async def fetch(self) -> None:
        async for artist in self._song.artists.all():
            self._artists.append(artist)
    
    @property
    def artists(self) -> str:
        if self._artists:
            return ", ".join([artist.name for artist in self._artists])
        raise RuntimeError
    
    @property
    def name(self) -> str:
        return self._song.name
    
    @property
    def title(self) -> str:
        return f"{self.artists} - {self.name}"
    
    @property
    def id(self) -> int:
        return self._song.id
