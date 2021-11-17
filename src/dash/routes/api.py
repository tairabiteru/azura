from core.conf import conf
from orm.revisioning import Revisioning

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__)


@routes.post("/api/voice/connect")
async def voice_connect(request):
    gid = request.json['gid']
    vid = request.json['vid']

    await request.app.ctx.bot.update_voice_state(gid, vid)
    info = await request.app.ctx.bot.lavalink.wait_for_full_connection_info_insert(gid)
    await request.app.ctx.bot.lavalink.create_session(info)

    json = {
        'response': 'success',
        'bot': request.app.ctx.bot.get_me().id
    }
    return sanic.response.json(json)


@routes.post("/api/voice/disconnect")
async def voice_disconnect(request):
    gid = request.json['gid']
    await request.app.ctx.bot.lavalink.destroy(gid)
    await request.app.ctx.bot.update_voice_state(gid, None)
    await request.app.ctx.bot.lavalink.wait_for_connection_info_remove(gid)
    await request.app.ctx.bot.lavalink.remove_guild_node(gid)
    await request.app.ctx.bot.lavalink.remove_guild_from_loops(gid)
    json = {
        'response': 'success',
        'bot': request.app.ctx.bot.get_me().id
    }
    return sanic.response.json(json)


@routes.post("/api/voice/play")
async def voice_play(request):
    gid = request.json['gid']
    uid = request.json['uid']
    query = request.json['query']
    track = await request.app.ctx.bot.lavalink.auto_search_tracks(query)
    track = track.tracks[0]
    await request.app.ctx.bot.lavalink.play(gid, track).requester(uid).queue()
    json = {
        'response': 'success',
        'bot': request.app.ctx.bot.get_me().id,
        'track': {
            'length': track.info.length,
            'uri': track.info.uri,
            'title': track.info.title,
            'author': track.info.author
        }
    }
    return sanic.response.json(json)


@routes.get("/api/voice/states")
async def voice(request):
    states = await request.app.ctx.bot.koe.voiceView()
    response = {'response': 'ACK', 'states': states}
    return sanic.response.json(response)
