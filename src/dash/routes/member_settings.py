from dash.oauth import require_authentication
from dash.websettings import MemberSettings, ValidationFailure
from orm.member import Member

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__)


@routes.get("/member")
@jinja.template("member.html")
@require_authentication
async def index(request):
    member = Member.obtain(request.ctx.session['uid'])
    settings = MemberSettings.obtain(request.app.ctx.bot, member)
    return {
        'member': member,
        'settings': settings.settings
    }


@routes.post("/member/save")
@require_authentication
async def save_settings(request):
    member = Member.obtain(request.ctx.session['uid'])
    settings = MemberSettings.obtain(request.app.ctx.bot, member)
    try:
        setting = settings.getSetting(request.json['setting'])
        settings.setSetting(setting, request.json['value'])
    except ValidationFailure as e:
        return sanic.response.text(f"Error: {str(e)}")

    return sanic.response.text(f"{setting.name} set to {request.json['value']}.")
