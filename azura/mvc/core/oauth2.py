"""Module containing OAuth2 functions for Discord

azura's website must be able to authenticate users so that she can know
who is logged in. This is most useful in the playback of clips, (where she
needs to know what channel you're in) and in the user settings page. (where she needs
to know whose set- ...you know what? I'll let you figure that one out.)

    * ENDPOINT - Endpoint of the Discord API
    * OAuth2Error - Generic error thrown when an issue occurs during the OAuth2 process
    * get_oauth2_code - Function which obtains an oauth2 code given a request
    * get_oauth2_token - Function which obtains an oauth2 token, given a request whose GET parameters contain an oauth2 code
    * refresh_oauth2_token - Function which refreshes an expired oauth2 token, similar to get_oauth2_token
    * obtain_uid - Function which uses the aforementioned functions to store a user's Discord ID in a Django session object
    * require_auth - Decorator for views which will automatically authenticate a user before allowing access to a page

The latter function is used to decorate Django function based views to provide a simple way to authenticate users.
The decorator works by automatically altering the session object with the request object to contain a key, 'uid'
which contains the authenticated user's Discord ID. This can be accessed within the view to perform further actions.
"""
import datetime
import urllib
from cryptography.fernet import Fernet
from django.http.response import HttpResponseRedirect
from django.shortcuts import redirect
import orjson as json

from ...core.conf import Config
from ...lib.utils import aio_post, aio_get, utcnow


conf = Config.load()

ENDPOINT = "https://discord.com/api"
REDIRECT_URI = "https://azura.tairaserver.net/auth"


class OAuth2Error(Exception):
    pass


def encrypt_state(state) -> str:
    key = Fernet(conf.mvc.fernet_key)
    return key.encrypt(json.dumps(state)).decode("utf-8")


def decrypt_state(ciphertext):
    key = Fernet(conf.mvc.fernet_key)
    return json.loads(key.decrypt(ciphertext.encode("utf-8")))


async def get_oauth2_code(request, state={}, scope="identify"):
    query = urllib.parse.urlencode({
        'client_id': request.bot.get_me().id,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': scope,
        'state': encrypt_state(state)
    })
    return redirect(f"{ENDPOINT}/oauth2/authorize?{query}")


async def get_oauth2_token(request, state={}, scope="identify"):
    if not request.GET.get("code", None):
        return await get_oauth2_code(request, state=state, scope=scope)

    if request.session.get("oauth2", None):
        if utcnow() > datetime.datetime.strptime("%x %X %z"):
            return await refresh_oauth2_token(request, scope=scope)

    data = {
        'client_id': request.bot.get_me().id,
        'client_secret': conf.mvc.client_secret,
        'grant_type': 'authorization_code',
        'code': request.GET.get('code'),
        'redirect_uri': REDIRECT_URI,
        'scope': scope,
        'state': encrypt_state(state)
    }

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    oauth2_resp = await aio_post(f"{ENDPOINT}/v6/oauth2/token", data=data, headers=headers, format="json")

    if 'error' in oauth2_resp:
        raise OAuth2Error(oauth2_resp['error'])
    
    oauth2_resp['token_expiry'] = (utcnow() + datetime.timedelta(seconds=oauth2_resp.pop("expires_in"))).strftime("%x %X %z")
    request.session['oauth2'] = oauth2_resp
    return request.session


async def refresh_oauth2_token(request, state={}, scope="identify"):
    data = {
        'client_id': request.bot.get_me().id,
        'client_secret': conf.mvc.client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': request.session['oauth2']['refresh_token'],
        'redirect_uri': REDIRECT_URI,
        'scope': scope,
        'state': encrypt_state(state)
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    oauth2_resp = await aio_post(f"{ENDPOINT}/v6/oauth2/token", data=data, headers=headers, format="json")

    if 'error' in oauth2_resp:
        raise OAuth2Error(oauth2_resp['error'])
    
    oauth2_resp['token_expiry'] = (utcnow() + datetime.timedelta(seconds=oauth2_resp.pop("expires_in"))).strftime("%x %X %z")
    request.session['oauth2'] = oauth2_resp
    return request.session


async def obtain_uid(request, state={}):
    if not request.session.get("oauth2", None):
        response = await get_oauth2_token(request, state=state)
        if isinstance(response, HttpResponseRedirect):
            return response
        
        request.session = response
    
    headers = {
        'Authorization': f"{request.session['oauth2']['token_type']} {request.session['oauth2']['access_token']}"
    }

    response = await aio_get(f"{ENDPOINT}/users/@me", headers=headers, format="json")
    request.session['uid'] = int(response['id'])


def require_auth(func):
    async def wrapper(request, *args, **kwargs):
        if not request.session.get("uid", None):
            response = await obtain_uid(request, state={'redirect': request.path})

            if response is not None:
                return response
        
        if request.GET.get("code", None):
            if len(request.GET) == 2:
                url = request.build_absolute_uri().split("?")[0]
            else:
                url = request.build_absolute_uri().replace(f"?code={request.GET.get('code')}", "")
            url = url.replace("http://", "https://")
            return redirect(url)
        return await func(request, *args, **kwargs)
    return wrapper


