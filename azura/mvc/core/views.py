from ...core.conf import Config

conf = Config.load()

from .utils import template
from asgiref.sync import sync_to_async


@template("index.html")
async def index(request):
    authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
    uid = request.session.get("uid", None)
    return {
        'avatar_url': request.bot.get_me().avatar_url,
        'name': request.bot.get_me().username,
        'version': await request.bot.get_version(),
        'display_admin': authenticated or uid == conf.owner_id
    }