import sanic
from sanic_jinja2 import SanicJinja2 as jinja


routes = sanic.Blueprint(__name__.replace(".", "_"))


@routes.get("/")
@jinja.template("index.html")
async def index(request):
    return {
        'bot': request.app.ctx.bot,
        'version': request.app.ctx.bot.revision.version
    }
