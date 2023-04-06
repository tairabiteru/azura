import koe
import sanic


routes = sanic.Blueprint(__name__.replace(".", "_"))


def require_child(func):
    async def wrapper(request, *args, **kwargs):
        if request.app.ctx.bot.type.value != "CHILD":
            raise ValueError(f"A function requiring a child bot was called with non-child bot {request.app.ctx.bot.name}.")
        return await func(request, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@routes.get("/favicon.ico")
async def favicon(request):
    return sanic.redirect("/static/favicon.ico")


@routes.post("/api/reinitialize")
@require_child
async def api_reinitialize(request):
    await request.app.ctx.bot.reinit()
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/connect")
@require_child
async def api_connect(request):
    args = list(request.json.values())
    try:
        await request.app.ctx.bot.koe.create_session(*args)
    except koe.ExistingSession:
        return sanic.response.json({'status': 'SESSION_EXISTS'})
    except koe.SessionBusy:
        return sanic.response.json({'status': 'BUSY'})
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/disconnect")
@require_child
async def api_disconnect(request):
    args = list(request.json.values())
    await request.app.ctx.bot.koe.destroy_session(args[1], must_exist=False)
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/play")
@require_child
async def api_play(request):
    query = request.json['query']
    requester = request.app.ctx.bot.cache.get_user(request.json['requester_id'])

    try:
        session = await request.app.ctx.bot.koe.get_session_from_voice_id(request.json['voice_id'])
    except koe.NoExistingSession:
        return sanic.response.json({'status': 'NO_EXISTING_SESSION'})

    await session.play(requester, query)
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/skip")
@require_child
async def api_skip(request):
    requester = request.app.ctx.bot.cache.get_user(request.json['requester_id'])
    by = request.json['by']
    to = request.json['to']
    requester = request.app.ctx.bot.cache.get_user(request.json['requester_id'])

    try:
        session = await request.app.ctx.bot.koe.get_session_from_voice_id(request.json['voice_id'])
    except koe.NoExistingSession:
        return sanic.response.json({'status': 'NO_EXISTING_SESSION'})
    await session.skip(requester, to=to, by=by)
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/volume/set")
@require_child
async def api_volume_set(request):
    user = request.app.ctx.bot.cache.get_user(request.json['user_id'])
    setting = request.json['setting']
    increment = request.json['increment']

    try:
        session = await request.app.ctx.bot.koe.get_session_from_voice_id(request.json['voice_id'])
    except koe.NoExistingSession:
        return sanic.response.json({'status': 'NO_EXISTING_SESSION'})
    await session.set_volume(user, setting=setting, increment=increment)
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/pause")
@require_child
async def api_pause_set(request):
    try:
        session = await request.app.ctx.bot.koe.get_session_from_voice_id(request.json['voice_id'])
    except koe.NoExistingSession:
        return sanic.response.json({'status': 'NO_EXISTING_SESSION'})
    await session.pause()
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/enqueue")
@require_child
async def api_enqueue(request):
    requester = request.app.ctx.bot.cache.get_user(request.json['requester_id'])
    playlist = request.json['playlist']
    shuffle = request.json['shuffle']
    mode = request.json['mode']
    user = request.json['user_id']

    if user is not None:
        user = request.app.ctx.bot.cache.get_user(user)

    try:
        session = await request.app.ctx.bot.koe.get_session_from_voice_id(request.json['voice_id'])
    except koe.NoExistingSession:
        return sanic.response.json({'status': 'NO_EXISTING_SESSION'})

    await session.enqueue(
        requester,
        playlist,
        shuffle=shuffle,
        mode=mode,
        user=user
    )
    return sanic.response.json({'status': 'OK'})


@routes.post("/api/destroy_session")
async def api_destroy_session(request):
    args = list(request.json.values())
    await request.app.ctx.bot.koe.destroy_session(args[1], send_termination=False)
    return sanic.response.json({'status': 'OK'})
