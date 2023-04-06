"""
Define the admin plugin.

The admin plugin contains commands which are both useful to server administrators
as well as the bot's maintainer.
"""

from core.conf import conf
from ext.utils import dirSize, getPublicIPAddr, lint, localnow, reduceByteUnit, strfdelta
from ext.ctx import getHideOrNone, ValidationMenu
from ext.pagination import PaginatedView

import orm.models as models

import hikari
import keikou
import os
import platform
import shutil
import sys


admin = keikou.Plugin("admin")
admin.description = f"Administrative commands. These commands are used for the administration of {conf.parent.name}."


@admin.command()
@keikou.command("bot", f"Commands related to {conf.parent.name}'s operation.")
@keikou.implements(keikou.SlashCommandGroup)
async def bot(ctx):
    pass


@bot.child()
@keikou.command("uptime", f"View {conf.parent.name}'s current uptime information.")
@keikou.implements(keikou.SlashSubCommand)
async def uptime(ctx):
    embed = hikari.embeds.Embed(title=f"{conf.parent.name}'s Current Uptime")
    embed.add_field(name="Time Since Initialization", value=strfdelta((localnow() - ctx.bot.last_initalization), '{%H}:{%M}:{%S}'))
    embed.add_field(name="Time Since API Connection", value=strfdelta((localnow() - ctx.bot.last_api_connection), '{%H}:{%M}:{%S}'))
    await ctx.respond(embed)


@bot.child()
@keikou.command("kill", f"Kill {conf.parent.name} completely. This is irreversable.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def kill(ctx):
    """
    **!!! WARNING !!!**
    Upon executing this command, {botname} will cease to work entirely, and this
    issue can only be fixed at the console! Be sure you know what you're doing.
    """
    msg = "You are about to issue a kill command. This action is **__IRREVERSABLE__** without console access!"
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])

    conf.logger.warning(f"Kill call by {ctx.author.username}.")
    await ctx.edit_last_response("🔌 Call to kill received. Shutting down now. Bye! 🔌", components=[])
    os.system(f"touch {os.path.join(conf.root_dir, 'lock')}")
    await ctx.bot.shutdown()


@bot.child()
@keikou.option("force", "Forces a restart, ignoring the linter. Can be DANGEROUS.", type=bool, default=False)
@keikou.option("bot", "Specify the name of the bot to reinitialize. Defaults to all.", type=str, default="all")
@keikou.command("reinitialize", f"Restart {conf.parent.name}.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def reinitialize(ctx):
    """
    Before restarting, {botname} will lint the codebase for errors. If errors are
    found, the reinitialization will be refused. Optionally, one can force the
    reinitialization, but without knowing the reason for the refusal, this can
    be dangerous, and result in {botname} failing to restart.
    """
    if ctx.options.force is not True:
        resp = await ctx.respond("🔍 Performing code inspection prior to reinitialization... 🔍")
        if errors := lint(os.path.join(os.getcwd(), "azura")):
            plural = "error" if len(errors) == 1 else "errors"
            menu = ValidationMenu()
            await ctx.edit_last_response(f"__❌ Reinitialization call refused ❌__\n{len(errors)} {plural} in upstream code.  Would you like to override?", components=menu.build())
            ctx.bot.logger.warning("Call to reinitialize failed due to the following errors in upstream code:")
            for error in errors:
                ctx.bot.logger.warning(f"[{error['number']}] [{error['filename']}] [Line #{error['lnum']}] {error['text']}")

            menu.start((await resp.message()))
            await menu.wait()

            if menu.result is False:
                return await ctx.edit_last_response("❌ Reinitialization call refused ❌", components=[])
            else:
                await ctx.edit_last_response("⚡ Use of force authorized. Reinitializing now. ⚡", components=[])
        else:
            await ctx.edit_last_response("⚡ Upstream code OK. Reinitializing now. ⚡")
    else:
        await ctx.respond("⚡ Use of force authorized. Reinitializing now. ⚡")

    if ctx.options.bot is None or ctx.options.bot == "all":
        ctx.bot.logger.warning(f"Reinitialization call by {ctx.author.username}. Reinitializing now...")
        await ctx.bot.reinit(ctx.get_channel())
    else:
        try:
            ctx.bot.logger.warning(f"Reinitialization call by {ctx.author.username}. Reinitializing {ctx.options.bot} now...")
            await ctx.bot.reinit_individual(ctx.options.bot)
        except ValueError as e:
            await ctx.edit_last_response(str(e))



@bot.child()
@keikou.option("lines", "The number of lines to show.", type=int, default=10)
@keikou.option("contains", "Filter lines by some term.", default=None)
@keikou.option("hide", "Whether or not the response should be hidden. Defaults to True.", type=bool, default=True)
@keikou.command("tail", "Show the last lines in the log file.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def tail(ctx):
    flags = getHideOrNone(ctx)

    lines = open("logs/bot.log", "r").readlines()
    lines = list([line.replace("```", "'''") for line in lines])

    pages = []
    msg = ""
    for line in reversed(lines):
        if len(line) + len(msg) > 1994:
            pages.append(f"```{msg}```")
            msg = line
        else:
            msg = line + msg

    if msg not in pages and msg != "":
        pages.append(f"```{msg}```")

    menu = PaginatedView(pages, page=len(pages)-1)
    resp = await ctx.respond(menu.current, flags=flags, components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()


@bot.child()
@keikou.command("info", f"Show information about {conf.parent.name}.")
@keikou.implements(keikou.SlashSubCommand)
async def info(ctx):
    latency = round((ctx.bot.heartbeat_latency * 1000), 1)
    ip = await getPublicIPAddr()

    embed = hikari.Embed(title=conf.parent.name, url=conf.dash.outfacing_url)
    pyver = sys.version_info
    embed.description = f"**Version {ctx.bot.revision.version}**\nRunning on {platform.python_implementation()} {pyver[0]}.{pyver[1]}.{pyver[2]}"
    embed.set_thumbnail(ctx.bot.get_me().avatar_url)

    lines = "{:,}".format(ctx.bot.revision.lines)
    chars = "{:,}".format(ctx.bot.revision.characters)
    commands = len(ctx.bot.prefix_commands) + len(ctx.bot.slash_commands)
    code_stats = f"Lines: {lines}\nChars: {chars}\nCommands: {commands}"
    embed.add_field("Code Statistics", value=code_stats)

    root = reduceByteUnit(dirSize(conf.root_dir))
    temp = reduceByteUnit(dirSize(conf.temp_dir))
    dirs = f"Root: {root}\nTemp: {temp}"
    embed.add_field("Directory Info", value=dirs)

    conn = f"Connecting IP: {ip}\nHeartbeat Period: {latency} ms"
    embed.add_field("Connection Info", value=conn)
    await ctx.respond(embed)


@bot.child()
@keikou.command("purge", "Purge all application commands. DANGEROUS.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def purge(ctx):
    """
    This is useful if some issue with slash commands occurs, but one should be
    aware that this command's execution tends to cause multiple validity errors
    with the Discord client until the API has been updated. As a result, the
    execution of this command should be considered **DANGEROUS**, and only used
    as a last resort.

    Also be aware that __**ZERO**__ validation will be performed when executing
    this command.
    """
    await ctx.bot.purge_application_commands()
    await ctx.respond("Purge completed. Restart to re-register.")


@admin.command()
@keikou.command("permissions", "Change, view, or check bot permissions.")
@keikou.implements(keikou.SlashCommandGroup)
async def permissions(ctx):
    """
    {botname}'s permissions architecture lies at the core of the command handling system. While it is complex, it is founded on only a few logical axioms. The permissions system relies on two concepts, *nodes* and *grant levels*.

    **Node**
    A node is simply a unique identifier attached to a command which allows it to be referenced uniquely, but heirarchially. A node is generally composed of the name of the plugin the command is in, followed by a dot, followed by the name of the command itself. For example, the node of the `/help` command that generated this message is `tools.help`, because it resides in the `tools` plugin, and the command's name is `help`.
    In previous versions of {botname}, that's all there was to it. However, slash commands allow for the creation of subgroups and subcommands which complicates nodes a bit more. If you have a command which is inside of a group, the node would be `plugin.group.command`. You can also have subgroups in groups. A command like that would have a node like so: `plugin.group.subgroup.command`. Thankfully, you aren't allowed to nest deeper than that, so that's as far as this goes.
    Some examples of this are commands like `/weather radiosonde`. In this case, the `/weather radiosonde` command is in the `weather` plugin, but it's also in a command group named `weather`. So the node of the `/weather radiosonde` command is `weather.weather.radiosonde`.

    **Grant Level**
    A grant level is a property attached to each command in {botname}'s source code. The grant level of each command effectively denotes the level of permission required to use the command. There are only two options for this, `explicit` and `implicit`:

    `explicit` - By default, __NO ONE__ can run explicit commands. To run such a command, you'd need to be *explicitly* allowed to run it.

    `implicit` - By default, __ANYONE__ can run implicit commands. One can be explicitly denied from using implicit commands, but by default, a person's permission to use it is *implied*.

    Let's look at an example, the `/bot kill` command. The `/bot kill` command has an `explicit` grant level. Makes sense, you probably don't want just anyone killing the bot. In order to run it, {botname} needs to be explicitly told who is allowed to run it. The node for `/bot kill` is `admin.bot.kill`. So to run it, their ACL would need to read `'admin.bot.kill': 'allow'`.

    **Wildcards**
    {botname} also supports wildcards in the ACL. Following the previous example, you could set someone's ACL to have `'admin.bot.kill': 'allow'` to let them run `/bot kill`. But you could also have `'admin.bot.*': 'allow'`. This would allow them to run not only `/bot kill`, but ***ANY*** command in the `/bot` command group.

    **Deny first**
    As a final note, {botname}'s permissions system works on a deny-first basis. This means that if any of a person's permissions deny them from using a command, they will not be allowed to use that command, period. This is true **EVEN IF** other parts of their ACL explicitly allow them to run the command.
    """
    pass


@permissions.child()
@keikou.option("value", "The value to set.", choices=["allow", "deny", "remove"])
@keikou.option("node", "The permissions node to modify.")
@keikou.option("role", "The role to manipulate.", type=hikari.Role, default=None)
@keikou.option("user", "The user to manipulate.", type=hikari.User, default=None)
@keikou.command("set", "Set permissions for a user or role.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def set(ctx):
    """
    For more information on {botname}'s permissions system, see the `/help`
    documentation on `/permissions`.
    """
    if ctx.options.user.id == ctx.bot.get_me().id:
        return await ctx.respond("Access is denied. I'll manage my own permissions, thanks.")
    if ctx.options.node not in ctx.bot.permissions.nodes:
        return await ctx.respond(f"Invalid permissions node `{ctx.options.node}`.")

    if ctx.options.user is None and ctx.options.role is None:
        return await ctx.respond("You must specify either a role or a user to modify.")
    if ctx.options.user is not None and ctx.options.role is not None:
        return await ctx.respond("You can only specify either a user or a role, not both.")

    if ctx.options.user is not None:
        object = await models.User.get_or_create(ctx.options.user)
        name = object.hikari_user.username
    elif ctx.options.role is not None:
        object = await models.RoleDatum.get_or_create(ctx.options.role)
        name = object.hikari_role.name

    if ctx.options.value == "remove":
        try:
            object.acl.pop(ctx.options.node)
            await object.save()
            return await ctx.respond(f"`{ctx.options.node}` removed from ACL for `{name}`.")
        except KeyError:
            return await ctx.respond(f"`{ctx.options.node}` not found in ACL for `{name}`.")

    for node, value in object.acl.items():
        if node == ctx.options.node:
            if value == ctx.options.value:
                return await ctx.respond(f"`{node}` is already set to `{value}` for `{name}`.")

    object.acl[ctx.options.node] = ctx.options.value
    await object.save()
    await ctx.respond(f"`{ctx.options.node}` set to `{ctx.options.value}` for `{name}`.")


@permissions.child()
@keikou.option("hide", "Whether or not output should be hidden. True by default.", type=bool, default=True)
@keikou.option("role", "The role to view.", type=hikari.Role, default=None)
@keikou.option("user", "The user to view.", type=hikari.User, default=None)
@keikou.command("acl", "Show the ACL for the specified user or role.")
@keikou.implements(keikou.SlashSubCommand)
async def acl(ctx):
    """
    Syntax: `{pre}{name}`

    **Node:** `{node}`
    **Grant Level:** `{grant_level}`

    __**Description**__
    Show the specified object's ACL. If no user is specified, it defaults to the author.
    """
    if ctx.options.user is None and ctx.options.role is None:
        object = await models.User.get_or_create(ctx.author)
    elif ctx.options.user is not None:
        object = await models.User.get_or_create(ctx.options.user)
    elif ctx.options.role is not None:
        object = await models.RoleDatum.get_or_create(ctx.options.role)
    else:
        return await ctx.respond("You cannot specify both a role and a user. Only one may be specified.")
    flags = getHideOrNone(ctx)

    msg = ""
    for node, value in object.acl.items():
        msg += f"{node}: {value}\n"

    if msg == "":
        return await ctx.respond("The ACL is empty.", flags=flags)
    await ctx.respond(f"```JSON\n{msg}```", flags=flags)


@admin.command()
@keikou.command("database", "Commands pertaining to database management.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashCommandGroup)
async def database(ctx):
    pass


@database.child()
@keikou.option("model", "The path from app to the model that is to be migrated.")
@keikou.command("migrate", "Migrate the database.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def migrate(ctx):
    from orm.connector import ORM
    import tortoise
    mysql = ORM.get_connection("mysql")
    await tortoise.utils.generate_schema_for_client(mysql, False)
    clips = await models.ClipDatum.all()
    for clip in clips:
        await clip.save(using_db=mysql)


@database.child()
@keikou.command("initialize", "Initialize the database to its defaults. VERY. DANGEROUS.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def initialize(ctx):
    """
    It is worth noting prior to describing anything that this is perhaps **__THE MOST DANGEROUS COMMAND__** that one can possibly execute.
    A database initialization operation should seldom take place. During an initialization, the following will happen:

    1. The existing database connection will be shut down.
    2. The existing database will be backed up.
    3. {botname} will restart, in the process, deleting the old database, and starting with a blank one.

    The fact that a backup is made is no reason to take solace. If extensive changes are made in the new database, that data becomes extremely difficult to migrate to any old copy. This operation should only be performed as a last resort, and with **EXTREME** caution.
    """
    msg = "You are about to initialize the database. This is perhaps **__THE MOST DANGEROUS COMMAND__** you can possibly invoke.\nWhen you initialize the database, the following will happen:\n\n1. The existing database connection will be shut down.\n2. The existing database will be backed up.\n3. I will restart, creating a new database in the process, and thereby WIPING all information from the existing database.\n\nAnyone invoking this command needs to understand the gravity of using it. Any information put into this new database will be FORFEIT in the event a mistake is made. Combining two databases like this is exceptionally hard. This command should really only be executed as a means to wipe the existing database, even though a backup is made."
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])

    conf.logger.warning(f"Database initialization call made by {ctx.author.username}.")
    await ctx.edit_last_response("⚡ Call to initialize database made. Restarting now. ⚡", components=[])
    await ctx.bot.close_database()
    shutil.move(os.path.join(conf.rootDir, "database.sqlite3"), os.path.join(conf.dbBackupDir, localnow().strftime("database_backup_%Y_%m_%d_%H_%M_%S.sqlite3")))
    await ctx.bot.reinit()


@database.child()
@keikou.command("backup", "Create a backup of the existing database.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def backup(ctx):
    """
    During a backup operation, the following will take place:

    1. The existing database connection will be shut down.
    2. The existing database will be backed up.
    3. {botname} will restart in order to re-form the database connection.

    While this command does not delete the existing database, it is still disruptive, and so should be executed with care.
    """
    msg = f"You are about to backup the database. While this is not necessarily dangerous, it is disruptive, as it requires a restart of {conf.parent.name}."
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])
    conf.logger.warning(f"Database backup call made by {ctx.author.username}.")
    await ctx.edit_last_response("⚡ Call to backup database made. Restarting now. ⚡", components=[])
    await ctx.bot.close_database()
    shutil.copyfile(os.path.join(conf.rootDir, "database.sqlite3"), os.path.join(conf.dbBackupDir, localnow().strftime("database_backup_%Y_%m_%d_%H_%M_%S.sqlite3")))
    await ctx.bot.reinit()


@database.child()
@keikou.command("test", "A testing command.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def test(ctx):
    """
    This command doesn't do anything in particular, but it is often used by the
    developer to obtain information about certain parts of the database subsystem.
    """
    # import json
    # import os
    # DIR = "/home/taira/azura4/storage/database/members/"

    # for file in os.listdir(DIR):
    #     with open(os.path.join(DIR, file), "r") as infile:
    #         data = json.load(infile)
    #         uid = data['uid']

    #         user = ctx.bot.cache.get_user(uid)
    #         if user is not None:
    #             user = await models.User.get_or_create(user)

    #             for name, contents in data['playlists'].items():
    #                 playlist = await models.Playlist.create(
    #                     owner=user,
    #                     name=name,
    #                     is_public=False
    #                 )

    #                 for entry in contents:
    #                     source = entry['generator']
    #                     title = entry['custom_title']
    #                     if not title:
    #                         print("Custom title is blank, searching...")
    #                         result = await ctx.bot.lavalink.auto_search_tracks(source)
    #                         track = result.tracks[0]
    #                         title = track.info.title
                        
    #                     start = entry['start']
    #                     end = entry['end']
    #                     entry = await models.PlaylistEntry.create(
    #                         source=source,
    #                         title=title,
    #                         start=start,
    #                         end=end
    #                     )
    #                     await entry.save()
    #                     await playlist.items.add(entry)
    #                     await playlist.save()
                
    #                 await user.playlists.add(playlist)
    #                 await user.save()
    pass

@admin.command()
@keikou.option("topic", "The topic to explain. This is most often the name of a command.", default=None)
@keikou.command("help", f"Explain various parts of {conf.parent.name}.")
@keikou.implements(keikou.SlashCommand)
async def help(ctx):
    """
    {botname}'s help command is designed to be as helpful as possible. There
    are multiple ways this command can be run. If you run `/help` without any
    options, {botname} will present you with the main help menu, where you can
    use selection boxes to move through every possible help topic {botname} has
    available.

    Alternatively, you can specify the `topic` option, to bring up a specific
    topic. When you do this, {botname} will recurse through every topic
    available, adding all matching topics to a list. If there's only one topic
    found, that one will be presented alone. Otherwise, she'll present you with
    a menu that asks you to specify which of the many topics you want to see.
    """
    topic = ctx.bot.help.resolveTopic(ctx.options.topic)
    if topic is not None:
        menu = keikou.TopicMenu(topic)
        components = menu.build() if topic.subtopics != [] else []
        resp = await ctx.respond(topic.embed, components=components)
        if topic.subtopics != []:
            menu.start((await resp.message()))
            await menu.wait()
    else:
        return await ctx.respond(f"I couldn't find a matching help topic using the query `{ctx.options.topic}`. Try running `/help` alone.")


def load(bot):
    bot.add_plugin(admin)


def unload(bot):
    bot.remove_plugin(admin)
