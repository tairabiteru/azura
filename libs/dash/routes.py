"""Main routing file for the dashboard."""

from libs.core.conf import settings
from libs.dash.oauth import handleIdentity
from libs.orm.server import Servers
from libs.orm.revisioning import Revisioning
from libs.orm.member import Member
from libs.orm.playlist import PlaylistEntry
from libs.ext.utils import serializeTimestamp

from aiohttp import web
from aiohttp_jinja2 import template
import discord
import os


routes = web.RouteTableDef()


@routes.get("/")
@template("index.html")
async def index(request):
    """Handle main landing page."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    # Prevents `?code=` from being in URL.
    # It just causes problems.
    if 'code' in request.rel_url.query:
        raise web.HTTPFound("/")

    member = Member.obtain(uid)
    return {'playlists': member.playlists}

@routes.post("/api/save-playlist")
async def api(request):
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    if data['name'].strip() == "":
        return web.Response(text="Error: You must specify a playlist name.")

    if data['action'] == "create" and member.playlist_exists(data['id']):
        return web.Response(text=f"Error: A playlist named \"{data['id']}\" already exists.")

    plentries = []
    for i, entry in enumerate(data['entries']):
        if not entry[1]:
            return web.Response(text=f"Error on row {i+1}: The generator is a required field.")

        try:
            for j in (2, 3):
                if not entry[j]:
                    entry[j] = 0 if j == 2 else -1
                else:
                    entry[j] = serializeTimestamp(entry[j])
        except ValueError:
            field = "start time" if j == 2 else "end time"
            return web.Response(text=f"Error on row {i+1}: Invalid {field}.")

        entry = PlaylistEntry(custom_title=entry[0], generator=entry[1], start=entry[2], end=entry[3])
        plentries.append(entry)

    if data['id'] == data['name'].strip():
        member.playlists[data['id']] = plentries
    else:
        del member.playlists[data['id']]
        member.playlists[data['name'].strip()] = plentries
    member.save()
    return web.Response(text="Playlist saved successfully!")

@routes.post("/api/delete-playlist")
async def api(request):
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    try:
        del member.playlists[data['id']]
    except KeyError:
        return web.Response(text=f"Error: Playlist '{data['id']}' not found in database. (Try reloading the page.)")
    member.save()
    return web.Response(text="Playlist successfully deleted.")
