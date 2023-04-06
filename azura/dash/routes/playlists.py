from dash.oauth import require_authentication

import orm.models as models

import sanic
from sanic_jinja2 import SanicJinja2 as jinja
import tortoise


routes = sanic.Blueprint(__name__.replace(".", "_"))


@routes.get("/playlists")
@jinja.template("playlists.html")
@require_authentication
async def playlists(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))

    playlists = await user.playlists.all()
    for i in range(0, len(playlists)):
        playlists[i].entries = await playlists[i].items.all()

    return {'playlists': playlists}


@routes.post("/playlists/get")
@require_authentication
async def playlists_get(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))
    playlist = (await user.playlists.filter(id=int(request.json['playlist_id'])))[0]
    return sanic.response.json((await playlist.serialize()))


@routes.post("/playlists/delete")
@require_authentication
async def playlists_delete(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))
    playlist = (await user.playlists.filter(id=int(request.json['id'])))[0]
    items = await playlist.items.all()
    for item in items:
        await item.delete()
    await playlist.delete()
    return sanic.response.json({'status': 'success'})


@routes.post("/playlists/save")
@require_authentication
async def playlists_save(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))
    
    try:
        if request.json['id'] == -1:
            playlist = await models.Playlist.create(
                owner=request.ctx.session['uid'],
                name=request.json['name'],
                description=request.json['description']
            )
            await user.playlists.add(playlist)
        else:
            playlist = (await user.playlists.filter(id=int(request.json['id'])))[0]
            playlist.name = request.json['name']
            playlist.description = request.json['description']
            await playlist.save()
    except tortoise.exceptions.IntegrityError:
        verb = "creating" if request.json['id'] == -1 else "saving"
        return sanic.response.json({
            'status': 'error',
            'reason': f"Error {verb} playlist: A playlist with the name '{request.json['name']}' already exists."
        })

    items = await playlist.items.all()
    await playlist.items.clear()
    times = max(len(items), len(request.json['items']))

    for i in range(0, times):
        if i > (len(request.json['items']) - 1):
            old_item = items[i]
            await old_item.delete()
            continue
        
        try:
            old_item = items[i]
            await old_item.delete()
        except IndexError:
            pass

        item = request.json['items'][i]
        new_item = await models.PlaylistEntry.create(
            source=item['source'],
            title=item['name']
        )
        new_item.start_timestamp = item['start']
        new_item.end_timestamp = item['end']
        await new_item.save()
        await playlist.items.add(new_item)

    await playlist.save()
    return sanic.response.json({'status': 'success'})