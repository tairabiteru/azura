from asgiref.sync import sync_to_async
import datetime 
from django.http import HttpResponse, JsonResponse
from django.db.utils import IntegrityError
import koe
import orjson as json
import types
import typing

from ..core.utils import template
from ..core.oauth2 import require_auth
from ...lib.utils import strfdelta
from ..music.models import Song, Artist, Library, Playlist
from ..discord.models import User
from ..discord.middleware import DiscordAwareHttpRequest as HttpRequest


def get_voice_state_for_user(bot, user):
    for guild, user_state in bot.cache.get_voice_states_view().items():
        for u, state in user_state.items():
            if u == user:
                return guild, state
    return None, None


async def get_session_or_none_from_uid(bot, user) -> koe.Session | None:
    guild, state = get_voice_state_for_user(bot, user)
    
    if guild is None:
        return None
    if state is None:
        return None
    
    return await bot.koe.get_session_or_none_by(guild_id=guild)


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


@require_auth
@template("player.html")
async def get_player(request):
    uid = request.session.get("uid", None)
    return {

    }


@require_auth
@template("player_templ.html")
async def get_player_templ(request):
    uid = request.session.get("uid")
    
    session = await get_session_or_none_from_uid(request.bot, uid)
    session = SessionProxy(session)
    await session.fetch()
        
    return {
        'session': session
    }


@require_auth
@template("upload.html")
async def upload_file(request: HttpRequest) -> dict[str, typing.Any]:
    artists = []
    async for artist in Artist.objects.all():
        artists.append(artist)
    
    if request.method == 'POST':
        for fname, file in request.FILES.items():
            song_data = request.POST[fname]
            song_data = json.loads(song_data)
            
            try:
                song = await Song.objects.aget(name=song_data['name'])
                
                artists = []
                for artist in song_data['artists']:
                    try:
                        artist = await Artist.objects.aget(name=artist)
                        contains = await song.artists.acontains(artist)
                        if not contains:
                            raise Song.DoesNotExist
                    except Artist.DoesNotExist:
                        raise Song.DoesNotExist
                
            except Song.DoesNotExist:
                lib = await Library.objects.aget(name="Society of Spilled Milk")
                song = Song(name=song_data['name'], library=lib)
                await sync_to_async(song.file.save)(file.name, file)
                await song.asave()
                
                for artist in song_data['artists']:
                    try:
                        artist = await Artist.objects.aget(name=artist)
                        await song.artists.aadd(artist)
                    except Artist.DoesNotExist:
                        artist = Artist(name=artist)
                        await artist.asave()
                        await song.artists.aadd(artist)        

    return {'artists': artists}


@require_auth
@template("songs.html")
async def get_songs(request: HttpRequest):
    if request.method == 'POST':        
        term = request.POST.get("term")
        
        if term in ["", " ", None]:
            return {'songs': []}
        
        assert term is not None
        songs = await Song.search(term)
        songs = list([item[1] for item in songs])
        proxies = []
    
        for song in songs:
            song_proxy = SongProxy(song)
            await song_proxy.fetch()
            proxies.append(song_proxy)
            
        return {'songs': proxies}
    return {'songs': []}
    

@require_auth
async def update_player(request: HttpRequest):
    uid = request.session.get("uid")
    session = await get_session_or_none_from_uid(request.bot, uid)
    if session is None:
        return HttpResponse("NX-VOICE")
    
    action = request.POST.get("action")
    
    if action == "play":
        await session.toggle_pause()
    
    if action == "adv1":
        await session.skip(by=1, user_id=uid)
    if action == "adv-1":
        await session.skip(by=-1, user_id=uid)
    if action == "search":
        songs = await Song.search(request.POST["song"])
        track = await request.bot.koe.load_tracks(songs[0][1].file.path)
        assert isinstance(track, koe.Track)
        await session.enqueue(track, user_id=uid)
        return HttpResponse("")
    if action == "vol":
        vol = int(request.POST["volume"])
        await session.set_volume(vol, user_id=uid)
    if action == "enqueue":
        song_id = int(request.POST["song"])
        song = await Song.objects.aget(id=song_id)
        track = await request.bot.koe.load_tracks(song.file.path)
        await session.enqueue(track, user_id=uid)
    if action == "seek":
        if session._current_track is None:
            return HttpResponse("OK")
        
        fraction = int(request.POST["position"]) / 10000
        position = int(session._current_track.info.length * fraction)
        await session.seek(millis=position, user_id=uid)
    if action == "skipto":
        pos = request.POST["position"]
        pos = int(pos)
        await session.skip(to=pos, user_id=uid)
    
    if action == "rept":
        mode = await session.get_repeat_mode()
        if mode is koe.RepeatMode.NONE:
            mode = koe.RepeatMode.ALL
        elif mode is koe.RepeatMode.ALL:
            mode = koe.RepeatMode.ONE
        else:
            mode = koe.RepeatMode.NONE
        await session.set_repeat_mode(mode)
    
    return HttpResponse("OK")


@require_auth
@template("playlists.html")
async def playlists(request: HttpRequest):
    owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
    playlists = []
    songs = []
    async for playlist in Playlist.objects.filter(owner=owner):
        playlists.append(playlist)
        
        
    async for song in Song.objects.all():
        proxy = SongProxy(song)
        await proxy.fetch()
        songs.append(proxy)
        
    return {'playlists': playlists, 'songs': songs}


@require_auth
@template("playlist_templ.html")
async def get_playlist(request: HttpRequest):
    owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
    playlist_id = int(request.POST['playlist_id'])
    
    if playlist_id == -1:
        playlist = types.SimpleNamespace()
        playlist.id = -1
        playlist.name, playlist.description = "", ""
        entry = types.SimpleNamespace()
        entry.title, entry.start, entry.end = "", "", ""
        entries = [entry]

    else:
        playlist = await Playlist.objects.aget(owner=owner, id=playlist_id)
        entries = []
    
        async for song in playlist.songs.all():
            proxy = SongProxy(song)
            await proxy.fetch()
            entries.append(proxy)
    
    return {'playlist': playlist, 'entries': entries}


@require_auth
async def delete_playlist(request: HttpRequest) -> HttpResponse:
    owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
    data = json.loads(request.POST['data'])
    id = int(data['playlist_id'])
    playlist = await Playlist.objects.aget(owner=owner, id=id)
    await playlist.adelete()
    return JsonResponse({'status': 'success'})


@require_auth
async def save_playlist(request: HttpRequest) -> HttpResponse:
    owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
    data = json.loads(request.POST['data'])
    data['playlist_id'] = int(data['playlist_id'])

    if data['playlist_id'] == -1:
        playlist = Playlist(
            owner=owner,
            name=data['name'],
            description=data['description']
        )
        
        try:
            await playlist.asave()
        except IntegrityError:
            return JsonResponse({'status': 'error', 'reason': 'A playlist with that name already exists.'})
        
        for song in data['songs']:
            id = int(song['id'].split("_")[-1])
            start = song['start']
            end = song['end']
            song = await Song.objects.aget(id=id)
            await playlist.songs.aadd(song)
        await playlist.asave()
    
        return JsonResponse({'status': 'reload', 'reason': 'Playlist created. The page will now reload.'})

    playlist = await Playlist.objects.aget(id=data['playlist_id'], owner=owner)
    namechange = False
    
    if data['name'] != playlist.name:
        namechange = True
        playlist.name = data['name']
    
    playlist.description = data['description']
    await playlist.songs.aclear()
    
    for song in data['songs']:
        id = int(song['id'].split("_")[-1])
        start = song['start']
        end = song['end']
        song = await Song.objects.aget(id=id)
        await playlist.songs.aadd(song)

    await playlist.asave()
    
    if namechange:
        return JsonResponse({'status': 'reload', 'reason': 'Playlist name changed. The page will now reload.'})
    
    return JsonResponse({'status': 'success'})
        