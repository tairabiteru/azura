from core.conf import conf
from dash.oauth import require_authentication
from dash.websettings import ServerSettings, ValidationFailure
from orm.server import Server

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__)


@routes.get("/server")
@jinja.template("server.html")
@require_authentication
async def index(request):
    server = Server.obtain(294260795465007105)
    settings = ServerSettings.obtain(request.app.ctx.bot, server)
    authorized = int(request.ctx.session['uid']) == conf.ownerID
    return {
        'authorized': authorized,
        'server': server,
        'settings': settings.settings
    }


@routes.post("/server/save")
@require_authentication
async def save_settings(request):
    if int(request.ctx.session['uid']) != conf.ownerID:
        return sanic.response.text("Nice cock.")

    server = Server.obtain(294260795465007105)
    settings = ServerSettings.obtain(request.app.ctx.bot, server)
    try:
        setting = settings.getSetting(request.json['setting'])
        settings.setSetting(setting, request.json['value'])
    except ValidationFailure as e:
        return sanic.response.text(f"Error: {str(e)}")

    return sanic.response.text(f"{setting.name} set to {request.json['value']}.")
