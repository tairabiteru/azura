from dash.oauth import require_authentication

import orm.models as models

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__.replace(".", "_"))


@routes.get("/user")
@jinja.template("user.html")
@require_authentication
async def index(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))
    settings = await user.get_settings()

    return {
        'user': user,
        'setting_objects': settings,
    }


@routes.post("/user/save")
@require_authentication
async def save_settings(request):
    user = await models.User.get_or_create(int(request.ctx.session['uid']))
    await user.set_settings(request.json)
    return sanic.response.text(f"Set to {request.json['value']}.")
