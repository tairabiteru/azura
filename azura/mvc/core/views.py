from asgiref.sync import sync_to_async
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound, FileResponse
from django.conf import settings
import os

from ...core.conf import Config
from ..core.oauth2 import decrypt_state
from .utils import template


conf = Config.load()


async def auth(request):
    state = request.GET.get('state')
    state = decrypt_state(state)
    code = request.GET.get('code')
    return redirect(f"{state['redirect']}?code={code}")


@template("index.html")
async def index(request):
    authenticated = await sync_to_async(lambda: request.user.is_authenticated)()
    uid = request.session.get("uid", None)
    return {
        'avatar_url': request.bot.get_me().make_avatar_url(),
        'name': request.bot.get_me().username,
        'version': f"v{request.bot.conf.version} '{request.bot.conf.version_tag}'",
        'display_admin': authenticated or uid == conf.owner_id
    }


@login_required
def protected_file(request: HttpRequest) -> HttpResponse | FileResponse:
    component = request.build_absolute_uri().split("/uploads/cabinet/")[-1]
    file = settings.MEDIA_ROOT / "cabinet/"
    file = file / component

    if not os.path.exists(file):
        return HttpResponseNotFound("File not found")
    
    response = FileResponse(open(file, "rb"))
    response['Content-Disposition'] = "attachment; filename=" + str(file).split("/")[-1]
    return response