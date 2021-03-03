"""File containing utility functions pertaining to the dash."""

from aiohttp import web


def cleanGetParams(request):
    """Remove get params to keep URL clean."""
    if 'code' in request.rel_url.query:
        raise web.HTTPFound(str(request.rel_url).split("?")[0])
