from core.conf import conf
from orm.revisioning import Revisioning

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__)


@routes.get("/")
@jinja.template("index.html")
async def index(request):
    revisioning = Revisioning.obtain()
    return {
        'bot': request.app.ctx.bot,
        'version': revisioning.current
    }


@routes.get("/gate")
async def gateway(request):
    return sanic.response.redirect(conf.dash.serverInvite)
