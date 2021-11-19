from core.conf import conf
from ext.koe.koe import LocalKoeSession
from ext.koe.exceptions import NoExistingSession
from orm.revisioning import Revisioning

import hikari
import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__)


@routes.post("/api/session/delete")
async def session_delete(request):
    vid = request.json['vid']

    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.delete()
    return sanic.response.json({'response': 'success'})


@routes.post("/api/voice/connect")
async def voice_connect(request):
    gid = request.json['gid']
    vid = request.json['vid']
    cid = request.json['cid']

    session = LocalKoeSession(request.app.ctx.bot, gid, vid, cid)
    await session.connect()

    return sanic.response.json({'response': 'success'})


@routes.post("/api/voice/disconnect")
async def voice_disconnect(request):
    vid = request.json['vid']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.disconnect()
    return sanic.response.json({'response': 'success'})


@routes.post("/api/voice/play")
async def voice_play(request):
    vid = request.json['vid']
    uid = request.json['uid']
    query = request.json['query']

    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.play(uid, query)
    return sanic.response.json({'response': 'success'})


@routes.post("/api/voice/pause")
async def voice_pause(request):
    vid = request.json['vid']
    setting = request.json['setting']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.pause(setting)
    return sanic.response.json({'response': 'success'})


@routes.post("/api/voice/volume")
async def voice_pause(request):
    vid = request.json['vid']
    setting = request.json['setting']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)

    return sanic.response.json({'response': 'success'})


@routes.get("/api/voice/states")
async def voice(request):
    states = await request.app.ctx.bot.koe.voiceView()
    response = {'response': 'ACK', 'states': states}
    return sanic.response.json(response)
