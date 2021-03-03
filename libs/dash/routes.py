"""Main routing file for the dashboard."""

from libs.dash.oauth import handleIdentity
from libs.dash.utils import cleanGetParams
from libs.orm.revisioning import Revisioning
from libs.orm.member import Member, Equalizer
from libs.orm.playlist import PlaylistEntry
from libs.ext.utils import serializeTimestamp

from aiohttp import web
from aiohttp_jinja2 import template


routes = web.RouteTableDef()


def get_member(bot, member):
    """Obtain a member from all possible members."""
    for guild in bot.guilds:
        for m in guild.members:
            if member.uid == m.id:
                return m
    return None


async def updateEq(bot, member):
    """Update the equalizer given the member."""
    member_obj = get_member(bot, member)
    music = bot.get_cog('Music')
    if member_obj.voice.channel is None:
        return

    player = music.get_player(member_obj.guild)
    await player.set_equalizer(member.currentEq.wavelinkEQ)
    player.equalizer_name = member.currentEq.name


@routes.get("/")
@template("index.html")
async def index(request):
    """Handle landing page."""
    return {'bot': request.app.bot, 'version': Revisioning.obtain().current}


@routes.get("/settings")
@template("settings.html")
async def settings_page(request):
    """Handle settings page."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']
    cleanGetParams(request)

    member = Member.obtain(uid)

    return {'bot': request.app.bot, 'member': member}


@routes.get("/playlists")
@template("playlists.html")
async def playlists(request):
    """Handle playlist page."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    cleanGetParams(request)

    member = Member.obtain(uid)
    return {'playlists': member.playlists}


@routes.post("/api/save-playlist")
async def api_saveplaylist(request):
    """
    Handle AJAX requests to save playlists.

    This handles both changes to playlists, and changes to the names
    of playlists.
    """
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    if data['name'].strip() == "":
        return web.Response(text="Error: You must specify a playlist name.")

    if data['action'] == "create" and member.playlist_exists(data['id']):
        return web.Response(text=f"Error: A playlist named \"{data['id']}\" already exists.")

    plentries = []
    repeats = []
    for i, entry in enumerate(data['entries']):
        if not entry[1]:
            return web.Response(text=f"Error on row {i+1}: The generator is a required field.")

        # Check for invalid timestamps.
        try:
            for j in (2, 3):
                if not entry[j]:
                    entry[j] = 0 if j == 2 else -1
                else:
                    entry[j] = serializeTimestamp(entry[j])
        except ValueError:
            field = "start time" if j == 2 else "end time"
            return web.Response(text=f"Error on row {i+1}: Invalid {field}.")

        # Check for repeats in title or generator.
        repeats_in_title = list([e[0] for e in data['entries']]).count(entry[0])
        repeats_in_gener = list([e[1] for e in data['entries']]).count(entry[1])
        if repeats_in_gener > 1 or repeats_in_title > 1:
            repeats.append(str(i+1))

        entry = PlaylistEntry(custom_title=entry[0], generator=entry[1], start=entry[2], end=entry[3])
        plentries.append(entry)

    if len(repeats) != 0:
        resp = "Error: The following rows have repeats in the title or generator:"
        return web.Response(text=resp + ", ".join(repeats))

    if data['id'] == data['name'].strip():
        member.playlists[data['id']] = plentries
        member.save()
    else:
        del member.playlists[data['id']]
        member.playlists[data['name'].strip()] = plentries
        member.save()
        return web.Response(text="Playlist name updated!")

    return web.Response(text="Playlist saved successfully!")


@routes.post("/api/delete-playlist")
async def api_deleteplaylist(request):
    """Handle AJAX request to delete playlist."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    try:
        del member.playlists[data['id']]
    except KeyError:
        return web.Response(text=f"Error: Playlist '{data['id']}' not found in database. (Try reloading the page.)")
    member.save()
    return web.Response(text="Playlist successfully deleted.")


@routes.post("/api/settings/save")
async def api_settings_save(request):
    """Handle AJAX request to save settings."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    for setting, value in data.items():
        valid, range = member.settingInRange(setting, value)
        if not valid:
            return web.Response(text=f"Error: Invalid value for {setting}. Must be between {range[0]} and {range[1]}.")
        setattr(member.settings, setting, value)

    await updateEq(request.app.bot, member)
    member.save()
    return web.Response(text="Settings successfully saved.")


@routes.post("/api/eq/create")
async def api_eq_create(request):
    """Handle AJAX request to create an equalizer."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()

    eq = member.getEq(data['name'])
    if eq:
        return web.Response(text=f"Error: An equalizer named '{data['name']}' already exists.")

    data['levels'] = member.getEq(data['based_on']).levels if data['based_on'] is not None else Equalizer.DEFAULTS
    eq = Equalizer.buildFromJSON(data)

    member.equalizers.append(eq)
    member.save()
    return web.Response(text="New equalizer successfully made.")


@routes.post("/api/eq/obtain")
async def api_eq_obtain(request):
    """Handle AJAX request to obtain equalizer."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()
    eq = member.getEq(data['name'])

    if not eq:
        return web.json_response({'response': f"Error: No equalizer named '{data['name']}'."})

    response = {
        'response': 'success',
        'name': eq.name,
        'description': eq.description,
        'levels': eq.levels
    }
    return web.json_response(response)


@routes.post("/api/eq/change")
async def api_eq_change(request):
    """Handle AJAX request to change equalizers."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()
    eq = member.getEq(data['name'])

    if not eq:
        return web.Response(text=f"Error: an equalizer named '{data['name']}' does not exist.")

    member.current_eq = eq.name
    await updateEq(request.app.bot, member)
    member.save()

    return web.Response(text="Equalizer successfully changed.")


@routes.post("/api/eq/delete")
async def api_eq_delete(request):
    """Handle AJAX request to delete an equalizer."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()
    eq = member.getEq(data['name'])

    if not eq:
        return web.Response(text=f"Error: No equalizer named '{data['name']}'.")

    if eq.name == member.current_eq:
        if len(member.equalizers) == 1:
            return web.Response(text="Error: You cannot delete your last equalizer.")
        else:
            member.current_eq = member.equalizers[0].name

    member.equalizers = list([e for e in member.equalizers if e.name != eq.name])
    await updateEq(request.app.bot, member)
    member.save()

    return web.Response(text="Equalizer successfully deleted.")


@routes.post("/api/eq/levelset")
async def api_eq_levelset(request):
    """Handle AJAX request to set the levels of an equalizer."""
    session = await handleIdentity(request, scope="identify")
    uid = session['uid']

    member = Member.obtain(uid)
    data = await request.json()
    eq = member.getEq(data['name'])

    if not eq:
        return web.json_response({'response': f"Error: No equalizer named '{data['name']}'."})

    eq.levels[data['band']] = data['level']
    eqs = []
    for e in member.equalizers:
        if e.name == eq.name:
            eqs.append(eq)
        else:
            eqs.append(e)
    member.equalizers = eqs
    await updateEq(request.app.bot, member)
    member.save()

    return web.json_response({'response': 'success'})
