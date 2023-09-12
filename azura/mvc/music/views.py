from ...core.conf import Config
conf = Config.load()

from ..core.utils import template
from ..core.oauth2 import require_oauth2
from ..discord.models import User
from .models import Playlist, PlaylistEntry

from django.http import JsonResponse
from django.db.utils import IntegrityError
import orjson as json
import types


@require_oauth2()
@template("playlists.html")
async def playlists(request):
    owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
    playlists = await owner.get_playlists()
    return {'playlists': playlists}


@template("entries.html")
@require_oauth2()
async def playlist_get(request):
    if request.method == "POST":
        playlist_id = int(request.POST['playlist_id'])
        
        if playlist_id == -1:
            playlist = types.SimpleNamespace()
            playlist.name = ""
            playlist.description = ""
            entry = types.SimpleNamespace()
            entry.title, entry.source, entry.start, entry.end = "", "", "", ""
            entries = [entry]
        else:
            playlist = await Playlist.objects.select_related("owner").aget(id=playlist_id)
            if playlist.owner.id != int(request.session['uid']):
                return

            entries = await playlist.get_entries()
        return {'playlist': playlist, 'entries': entries}


@require_oauth2()
async def playlist_delete(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        playlist = await Playlist.objects.select_related("owner").aget(id=int(data['playlist_id']))
        if playlist.owner.id != request.session['uid']:
            return JsonResponse({})
        
        await playlist.adelete()
        return JsonResponse({'status': 'success'})

@require_oauth2()
async def playlist_save(request):
    if request.method == "POST":
        owner, _ = await User.objects.aget_or_create(id=request.session['uid'])
        data = json.loads(request.body.decode("utf-8"))

        titles = []
        for entry in data['items']:
            if entry['name'].strip() == "":
                return JsonResponse({'status': 'error', 'reason': "One or more entries does not have a name."})
            if entry['name'].strip() in titles:
                return JsonResponse({'status': 'error', 'reason': f"The title '{entry['name'].strip()}' appears more than once. This is not allowed."})
            if entry['source'].strip() == "":
                return JsonResponse({'status': 'error', 'reason': "One or more entries does not have a source."})
            
            titles.append(entry['name'].strip())
            
        if data['id'] == -1:
            try:
                playlist = Playlist(
                    owner=owner,
                    name=data['name'],
                    description=data['description']
                )
                await playlist.asave()
            except IntegrityError:
                return JsonResponse({'status': 'error', 'reason': f"A playlist named '{data['name']}' already exists. Please use a different name."})

        else:
            playlist = await Playlist.objects.aget(id=int(data['id']), owner=owner)
            playlist.name = data['name']
            playlist.description = data['description']
            await playlist.asave()
        
        entries = await playlist.get_entries() 

        for entry in entries:
            await entry.adelete()

        for i in range(0, len(data['items'])):            
            item = data['items'][i]

            entry = PlaylistEntry(
                playlist=playlist,
                source=item['source'].strip(),
                title=item['name'].strip(),
                start=item['start'].strip(),
                end=item['end'].strip(),
                index=i
            )
            await entry.asave()
        
        return JsonResponse({'status': 'success'})
        
        
        
        

