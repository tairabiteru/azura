from dash.oauth import require_authentication

import orm.models as models

import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__.replace(".", "_"))


@routes.get("/guild")
@jinja.template("guild.html")
@require_authentication
async def index_GET(request):
    guilds = await models.Guild.all()
    available_guilds = []
    for guild in guilds:
        if guild.hikari_guild.owner_id == int(request.ctx.session['uid']):
            available_guilds.append(guild)

    return {
        'guilds': available_guilds,
        'guild': None,
        'settings': None
    }


@routes.post("/guild")
@jinja.template("guild.html")
@require_authentication
async def index_POST(request):
    guild = int(request.form['guilds'][0])
    guild = await models.Guild.get_or_create(guild)

    if guild.hikari_guild.owner_id != int(request.ctx.session['uid']):
        raise sanic.exceptions.Forbidden

    settings = await guild.get_settings()
    return {'guilds': [], 'guild': guild, 'settings': settings}


@routes.post("/guild/save")
@require_authentication
async def save_settings(request):
    guild = await models.Guild.get_or_create(int(request.json['gid']))

    if int(request.ctx.session['uid']) != guild.hikari_guild.owner_id:
        return sanic.response.text("Nice cock.")

    await guild.set_settings(request.json)
    return sanic.response.text("Success.")


@routes.get("/guild/tags/<guild>")
@jinja.template("guild_tags.html")
@require_authentication
async def tags_GET(request, guild):
    guild = await models.Guild.get_or_create(int(guild))

    if guild.hikari_guild.owner_id != int(request.ctx.session['uid']):
        raise sanic.exceptions.Forbidden

    roles = await guild.roledata.all()
    return {'guild': guild, 'roles': roles}


@routes.post("/guild/tags/save")
@require_authentication
async def save_settings_tags(request):
    guild = await models.Guild.get_or_create(int(request.json['gid']))

    if int(request.ctx.session['uid']) != guild.hikari_guild.owner_id:
        return sanic.response.text("Nice cock.")

    setting, id = tuple(request.json['setting'].split("_"))
    value = request.json['value']

    role = await models.RoleDatum.get_or_create(request.app.ctx.bot.cache.get_role(int(id)))
    if setting == "description":
        role.description = value
    elif setting == "delimiter":
        role.is_tag_delimiter_role = not role.is_tag_delimiter_role
    elif setting == "tag":
        role.is_tag_role = not role.is_tag_role
    elif setting == "autoassign":
        role.is_auto_assigned_on_join = not role.is_auto_assigned_on_join
    await role.save()
    return sanic.response.text("Success.")
