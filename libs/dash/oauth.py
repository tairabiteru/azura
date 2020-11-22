"""Module to handle Discord OAuth2 in aiohttp."""

from libs.core.conf import settings
from libs.ext.utils import localnow

import aiohttp
from aiohttp import web
from aiohttp_session import get_session
import datetime
import urllib


async def handleOAuth(request, scope=""):
    """
    Handle OAuth2.

    This function takes the request and attempts to perform OAuth2, but only
    does so when it's necessary. It behaves differently under a few
    circumstances:

    - If the correct OAuth2 data is present, and the token has not yet expired,
    it simply returns the session object.
    - If the token has expired, it uses the refresh token to get a new one, and
    returns the new session data.
    - If the session data is not present, it checks to see if a code is attached
    to the request. If one is, it uses the code to retrieve a token, then
    returns the session data.
    - If one is not attached, it redirects the user to the OAuth2 URL, and
    obtains the code so that it can be used to retrieve a token.
    """
    session = await get_session(request)
    try:
        session['token']
        refresh_token = session['refresh_token']
        session['token_type']
        expiry = session['token_expiry']
        scope = session['scope']
        if localnow() > datetime.datetime.strptime(expiry, "%x %X %z"):
            data = {
                'client_id': settings['bot']['id'],
                'client_secret': settings['bot']['secret'],
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'redirect_uri': str(request.url).replace("http://", "https://"),
                'scope': scope
            }
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            async with aiohttp.ClientSession() as session:
                async with session.post("https://discord.com/api/v6/oauth2/token", data=data, headers=headers) as r:
                    json = await r.json()
            session['token'] = json['access_token']
            session['refresh_token'] = json['refresh_token']
            session['token_type'] = json['token_type']
            expiry = localnow() + datetime.timedelta(seconds=json['expires_in'])
            session['token_expiry'] = expiry.strftime("%x %X %z")
            session['scope'] = json['scope']
        return session
    except KeyError:
        try:
            code = request.rel_url.query['code']
        except KeyError:
            query_data = {
                'client_id': settings['bot']['id'],
                'redirect_uri': str(request.url).replace("http://", "https://"),
                'response_type': 'code',
                'scope': scope
            }
            query = urllib.parse.urlencode(query_data)
            raise web.HTTPFound("https://discord.com/api/oauth2/authorize?" + query)
        data = {
            'client_id': settings['bot']['id'],
            'client_secret': settings['bot']['secret'],
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': str(request.url).split("?")[0].replace("http://", "https://"),
            'scope': scope
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        async with aiohttp.ClientSession() as sesh:
            async with sesh.post("https://discord.com/api/v6/oauth2/token", data=data, headers=headers) as r:
                json = await r.json()
        session['token'] = json['access_token']
        session['refresh_token'] = json['refresh_token']
        session['token_type'] = json['token_type']
        expiry = localnow() + datetime.timedelta(seconds=json['expires_in'])
        session['token_expiry'] = expiry.strftime("%x %X %z")
        session['scope'] = json['scope']
        return session


async def getUID(token, type=None):
    """Retrieve a user's UID using an OAuth2 token."""
    headers = {
        'Authorization': "{type} {token}".format(type=type, token=token)
    }
    async with aiohttp.ClientSession() as session:
        async with session.get("https://discordapp.com/api/users/@me", headers=headers) as r:
            return await r.json()


async def handleIdentity(request, scope):
    """
    Handle user identity.

    This function works with handleOAuth() to identify a user given the request
    from a particular view. It does this by checking to see if the user's UID
    is present in the session data. If it is not, it performs any OAuth2
    necessary to identify them, then returns the session object.
    """
    session = await get_session(request)
    try:
        session['uid']
        return session
    except KeyError:
        try:
            user = await getUID(session['token'], type=session['token_type'])
        except KeyError:
            session = await handleOAuth(request, scope)
            return await handleIdentity(request, scope)
        session['uid'] = user['id']
        return session
