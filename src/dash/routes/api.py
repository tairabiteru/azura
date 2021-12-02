from ext.koe.session import RemoteKoeSession, ChildKoeSession
from ext.koe.queue import PositionError
from ext.koe.exceptions import NoExistingSession


import sanic


routes = sanic.Blueprint(__name__)


# Children only
@routes.post("/api/bot/kill")
async def bot_kill(request):
    await request.app.ctx.bot.cycleState(kill=True)
    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/bot/reinit")
async def bot_reinit(request):
    await request.app.ctx.bot.cycleState()
    return sanic.response.json({'response': 'success'})


# Parent and children
@routes.post("/api/session/delete")
async def session_delete(request):
    vid = request.json['vid']
    try:
        session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
        if isinstance(session, ChildKoeSession):
            await session.delete()
        elif isinstance(session, RemoteKoeSession):
            await request.app.ctx.bot.koe.delSession(session)
    except NoExistingSession:
        pass
    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/connect")
async def voice_connect(request):
    gid = request.json['gid']
    vid = request.json['vid']
    cid = request.json['cid']

    session = ChildKoeSession(request.app.ctx.bot, gid, vid, cid)
    await session.connect()

    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/disconnect")
async def voice_disconnect(request):
    vid = request.json['vid']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.disconnect()

    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/stop")
async def voice_stop(request):
    vid = request.json['vid']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.stop()
    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/play")
async def voice_play(request):
    vid = request.json['vid']
    uid = request.json['uid']
    query = request.json['query']

    try:
        session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
        await session.play(uid, query)
        return sanic.response.json({'response': 'success'})
    except NoExistingSession:
        return sanic.response.json({'response': 'NoExistingSession'})


# Children only
@routes.post("/api/voice/pause")
async def voice_pause(request):
    vid = request.json['vid']
    setting = request.json['setting']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.pause(setting)
    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/volume")
async def voice_volume(request):
    vid = request.json['vid']
    setting = request.json['setting']
    session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
    await session.volume(setting)

    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/move/to")
async def voice_move_to(request):
    vid = request.json['vid']
    position = request.json['position']

    try:
        session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
        await session.move_to(position)
    except PositionError as e:
        return sanic.response.json({
            'response': 'PositionError',
            'message': str(e)
        })

    return sanic.response.json({'response': 'success'})


# Children only
@routes.post("/api/voice/move/by")
async def voice_move_by(request):
    vid = request.json['vid']
    positions = request.json['positions']
    stop = request.json['stop']
    try:
        session = await request.app.ctx.bot.koe.fromComponents(vid=vid, must_exist=True)
        await session.move_by(positions, stop=stop)
    except PositionError as e:
        return sanic.response.json({
            'response': 'PositionError',
            'message': str(e)
        })

    return sanic.response.json({'response': 'success'})


# Parent and children
@routes.get("/api/voice/states")
async def voice(request):
    states = await request.app.ctx.bot.koe.voiceView()
    response = {'response': 'ACK', 'states': states}
    return sanic.response.json(response)
