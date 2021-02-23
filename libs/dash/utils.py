from aiohttp import web


def cleanGetParams(request):
    if 'code' in request.rel_url.query:
        raise web.HTTPFound(str(request.rel_url).split("?")[0])
