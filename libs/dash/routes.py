"""Main routing file for the dashboard."""

from libs.core.conf import settings
from libs.dash.oauth import handleIdentity
from libs.orm.server import Servers
from libs.orm.revisioning import Revisioning
from libs.orm.member import Member

from aiohttp import web
from aiohttp_jinja2 import template
import discord
import os

routes = web.RouteTableDef()


def get_voice(bot, uid):
    """Obtain a user's current voice channel given the bot and the uid."""
    for guild in bot.guilds:
        for channel in guild.channels:
            if channel.type == discord.ChannelType.voice:
                for member in channel.members:
                    if member.id == int(uid):
                        return channel

@routes.get("/")
@template("index.html")
async def index(request):
    """Handle main landing page."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']
    member = Member.obtain(uid)
    playlists = {}
    for playlist in member.playlist_names:
        entries = member.entries_in_playlist(playlist)
        playlists[playlist] = entries
    return {'playlists': playlists}

@routes.post("/api")
async def api(request):
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']
    data = await request.text()
    data = data.replace("=on", "").split("&")
    print(data)
