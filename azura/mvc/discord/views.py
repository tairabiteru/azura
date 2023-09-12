from ...core.conf import Config
conf = Config.load()
from ..core.utils import template
from ..core.oauth2 import require_oauth2

from ..discord.models import User, Locale

import zoneinfo
from django.http import HttpResponse
import json


@require_oauth2()
@template("user.html")
async def user(request):
    ctx = {}
    user, _ = await User.objects.aget_or_create(id=request.session['uid'])
    user = await User.objects.select_related("locale_settings").aget(id=user.id)
    user.attach_bot(request.bot)
    await user.aresolve_all()

    ctx['user'] = {}
    ctx['user']['volume_step'] = user.volume_step
    ctx['user']['volume_step_desc'] = "How much the volume should be changed by when using buttons."
    ctx['user']['prompt_on_search'] = user.prompt_on_search
    ctx['user']['prompt_on_search_desc'] = "Whether or not a search should be performed when using the play command without a direct link."


    ctx['timezones'] = list(sorted(zoneinfo.available_timezones()))
    ctx['date_formats'] = Locale.DATE_FORMATS
    ctx['time_formats'] = Locale.TIME_FORMATS

    ctx['user'] = {}
    ctx['user']['avatar_url'] = user.obj.avatar_url
    ctx['user']['username'] = user.obj.username
    ctx['user']['general'] = {}
    ctx['user']['general']['volume_step'] = user.volume_step
    ctx['user']['general']['volume_step_desc'] = "How much the volume should be changed by when using buttons."
    ctx['user']['general']['prompt_on_search'] = user.prompt_on_search
    ctx['user']['general']['prompt_on_search_desc'] = "Whether or not a search should be performed when using the play command without a direct link."

    ctx['user']['locale'] = {}
    ctx['user']['locale']['timezone'] = user.locale_settings.timezone
    ctx['user']['locale']['timezone_desc'] = f"Your current timezone. Used whenever {conf.name} reports a date or time to you."
    ctx['user']['locale']['date_format'] = user.locale_settings.date_format
    ctx['user']['locale']['date_format_desc'] = f"Your preferred date format. {conf.name} will use this format whenever displaying a date."
    ctx['user']['locale']['time_format'] = user.locale_settings.time_format
    ctx['user']['locale']['time_format_desc'] = f"Your preferred time format. {conf.name} will use this format whenever displaying a time."
    return ctx


@require_oauth2()
async def save_user(request):
    data = json.loads(request.body.decode("utf-8"))
    user, _ = await User.objects.aget_or_create(id=request.session['uid'])
    user = await User.objects.select_related("locale_settings").aget(id=user.id)

    if data['setting'] in ['volume_step', 'prompt_on_search']:
        setattr(user, data['setting'], data['value'])
    else:
        setattr(user.locale_settings, data['setting'], data['value'])
    
    await user.asave()
    await user.locale_settings.asave()

    return HttpResponse(f"{data['setting']} changed to {data['value']}")