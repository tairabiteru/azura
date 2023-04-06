"""Module to handle Discord OAuth2 in aiohttp."""

from core.conf import conf
from ext.utils import localnow

import aiohttp
import sanic
import datetime
import urllib


ENDPOINT = "https://discord.com/api"


class OAuth2Error(Exception):
    """Raised when an error happens during the authentication process."""
    pass


async def getOAuth2Code(request, scope="identify"):
    query = urllib.parse.urlencode({
        'client_id': request.app.ctx.bot.get_me().id,
        'redirect_uri': request.url.replace("http://", "https://"),
        'response_type': 'code',
        'scope': scope
    })
    return sanic.response.redirect(f"{ENDPOINT}/oauth2/authorize?{query}")


async def getOAuth2Token(request, scope="identify"):
    if not request.args.get('code'):
        return await getOAuth2Code(request, scope=scope)

    if request.ctx.session.get('oauth2'):
        if localnow() > datetime.datetime.strptime(request.ctx.session['oauth2']['token_expiry'], "%x %X %z"):
            return await refreshOAuth2Token(request, scope=scope)

    redirect_uri = request.url.replace("http://", "https://").split("?")[0]

    data = {
        'client_id': request.app.ctx.bot.get_me().id,
        'client_secret': conf.dash.oauth_secret,
        'grant_type': 'authorization_code',
        'code': request.args.get('code'),
        'redirect_uri': redirect_uri,
        'scope': scope
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{ENDPOINT}/v6/oauth2/token", data=data, headers=headers) as response:
            data = await response.json()

    if 'error' in data:
        raise OAuth2Error(data['error'])

    request.ctx.session['oauth2'] = {}
    request.ctx.session['oauth2']['access_token'] = data['access_token']
    request.ctx.session['oauth2']['refresh_token'] = data['refresh_token']
    request.ctx.session['oauth2']['token_type'] = data['token_type']
    request.ctx.session['oauth2']['token_expiry'] = (localnow() + datetime.timedelta(seconds=data['expires_in'])).strftime("%x %X %z")
    request.ctx.session['oauth2']['scope'] = data['scope']
    return request.ctx.session


async def refreshOAuth2Token(request, scope="identify"):
    data = {
        'client_id': request.app.ctx.bot.get_me().id,
        'client_secret': conf.dash.oauth_secret,
        'grant_type': 'refresh_token',
        'refresh_token': request.ctx.session['oauth2']['refresh_token'],
        'redirect_uri': request.url.replace("http://", "https://"),
        'scope': scope
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{ENDPOINT}/v6/oauth2/token", data=data, headers=headers) as response:
            data = await response.json()

    if 'error' in data:
        raise OAuth2Error(data['error'])

    request.ctx.session['oauth2']['access_token'] = data['access_token']
    request.ctx.session['oauth2']['refresh_token'] = data['refresh_token']
    request.ctx.session['oauth2']['token_type'] = data['token_type']
    request.ctx.session['oauth2']['token_expiry'] = (localnow() + datetime.timedelta(seconds=data['expires_in'])).strftime("%x %X %z")
    request.ctx.session['oauth2']['scope'] = data['scope']
    return request.ctx.session


async def ensureUID(request):
    if not request.ctx.session.get('oauth2'):
        r = await getOAuth2Token(request, scope="identify")
        if isinstance(r, sanic.response.HTTPResponse):
            return r
        request.ctx.session = r

    headers = {
        'Authorization': f"{request.ctx.session['oauth2']['token_type']} {request.ctx.session['oauth2']['access_token']}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ENDPOINT}/users/@me", headers=headers) as response:
            data = await response.json()
            request.ctx.session['uid'] = data['id']


def require_authentication(func):
    async def wrapper(*args, **kwargs):
        request = args[0]
        if not request.ctx.session.get('uid'):
            resp = await ensureUID(request)
            if resp is not None:
                return resp

        if 'code' in request.args:
            if len(request.args) == 1:
                url = request.url.split("?")[0]
            else:
                url = request.url.replace(f"code={request.args['code']}")
            return sanic.response.redirect(url)
        return await func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper
