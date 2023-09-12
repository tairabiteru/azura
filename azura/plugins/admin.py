from ..core.conf.loader import conf
import azura.keikou as keikou
from ..ext.utils import get_byte_unit, strfdelta, lint, dir_size
from ..ext.ctx import ValidationMenu, ReinitEmbed, PaginatedView
from ..mvc.internal.models import Revision
from ..mvc.discord.models import User, Role, PermissionsObject

import aiofiles
import hikari
import os
import platform
import sys


admin = keikou.Plugin("admin")
admin.description = f"Administrative commands, used for server administration, or for the administration of {conf.name}."


@admin.command()
@keikou.command("bot", f"Commands related to {conf.name}'s operation.")
@keikou.implements(keikou.SlashCommandGroup)
async def bot(ctx):
    pass


@bot.child()
@keikou.command("uptime", f"View {conf.name}'s uptime.")
@keikou.implements(keikou.SlashSubCommand)
async def uptime(ctx):
    embed = hikari.Embed(title=f"{conf.name}'s Current Uptime")
    inst = f"@{ctx.bot.last_instantiation.strftime('%x %X %Z')}, "
    inst += f"{strfdelta(ctx.bot.localnow() - ctx.bot.last_instantiation, '{%H}:{%M}:{%S}')} elapsed"
    embed.add_field("Instantiation", value=inst)
    api = f"@{ctx.bot.last_connection.strftime('%x %X %Z')}, "
    api += f"{strfdelta(ctx.bot.localnow() - ctx.bot.last_connection, '{%H}:{%M}:{%S}')} elapsed"
    embed.add_field("API Contact", value=api)
    return await ctx.respond(embed)


@bot.child()
@keikou.command("kill", f"Kill {conf.name} completely. This is irreversable.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def kill(ctx):
    f"""
    **!!! WARNING !!!
    Upon executing this command, {conf.name} will sease to work entirely, and
    this can only be corrected with console access! Be sure you know what you're doing.
    """
    msg = "You are about to issue a kill signal. This action is **__IRREVERSABLE__** without console access!"
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    await menu.start((await resp.message()))
    await menu.wait_for_input()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])
    
    await ctx.edit_last_response("🛑 Kill signal received, shutting down now. Bye! 🛑", components=[])
    await ctx.bot.kill(sender=ctx.author)


@bot.child()
@keikou.option("force", "Forces a reinitialization, ignoring the linter. Can be DANGEROUS.", type=bool, default=False)
@keikou.command("reinit", f"Reinitialize {conf.name}.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def reinit(ctx):
    f"""
    Before restarting, {conf.name} will lint the codebase for errors. If errors are
    found, the reinitialization will be refused. Optionally, one can force the
    reinitialization, but without knowing the reason for the refusal, this can be
    dangerous, and result in {conf.name} failing to restart.
    """
    resp = await ctx.respond("Inspecting codebase for errors...")
    if errors := lint(os.path.join(conf.root, "azura/")):
        plural = "error" if len(errors) == 1 else "errors"

        if ctx.options.force is False:
            menu = ValidationMenu()
            await ctx.edit_last_response(f"__❌ Reinitialization Refused ❌__\n{len(errors)} {plural} found in upstream code. Would you like to override?", components=menu.build())
            ctx.bot.logger.warning("Call to reinitialize failed due to the following errors in upstream code:")
            for error in errors:
                ctx.bot.logger.warning(f"[{error.number}] [{error.filename}] [Line #{error.lnum}] {str(error)}")
            await menu.start((await resp.message()))
            await menu.wait_for_input()

            if menu.result is False:
                return await ctx.edit_last_response("❌ Reinitialization call refused ❌", components=[])
            else:
                message = await ctx.edit_last_response("", embed=ReinitEmbed("pre", details="⚡ Override accepted, reinitializing in spite of errors ⚡"))
        else:
            message = await ctx.edit_last_response("", embed=ReinitEmbed("pre", details=f"⚡ Override used, reinitializing in spite of {len(errors)} {plural} ⚡"))
    else:
        message = await ctx.edit_last_response("", embed=ReinitEmbed("pre", details="⚡ Codebase is clean, reinitializing now ⚡"))
    
    await ctx.bot.reinit(sender=ctx.author, channel=ctx.get_channel(), message=message)


@bot.child()
@keikou.option("lines", "The number of lines to show.", type=int, default=10)
@keikou.option("contains", "Filter lines by a keyword.", default=None)
@keikou.option("hide", "Whether or not the response should be hidden. Defaults to True.", type=bool, default=True)
@keikou.option("type", "The log file to display. Defaults to bot.", default="azura", choices=["azura", "olivia", "access"])
@keikou.command("logs", "Displays the last lines in the long file.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def logs(ctx):
    flags = hikari.MessageFlag.EPHEMERAL if ctx.options.hide is True else hikari.MessageFlag.NONE

    try:
        async with aiofiles.open(os.path.join(conf.logs, f"{ctx.options.type}.log"), "r") as f:
            lines = await f.readlines()
    except FileNotFoundError:
        return await ctx.respond("No logs available.", flags=flags)
    
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
        
    pages = list(reversed(pages))
    
    menu = PaginatedView(pages, page=len(pages)-1)
    resp = await ctx.respond(menu.current, flags=flags, components=menu.build())
    await menu.start((await resp.message()))


@bot.child()
@keikou.command("info", f"Show information about {conf.name}.")
@keikou.implements(keikou.SlashSubCommand)
async def info(ctx):
    latency = round((ctx.bot.heartbeat_latency * 1000), 1)
    freq = round(1000.0 / latency, 5)
    ip = await ctx.bot.get_public_ip()
    pyver = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    version = await ctx.bot.get_version()

    embed = hikari.Embed(title=conf.name, url=f"https://{ctx.bot.domain}")
    embed.description = f"**Version {version}**\nRunning on {platform.python_implementation()} {pyver}"
    embed.set_thumbnail(ctx.bot.get_me().avatar_url)

    version = await Revision.objects.alatest()
    lines = "{:,}".format(version.lines)
    chars = "{:,}".format(version.chars)
    commands = len(ctx.bot.prefix_commands) + len(ctx.bot.slash_commands)
    code_stats = f"Lines: {lines}\nChars: {chars}\nCommands: {commands}"
    embed.add_field("Code Statistics", value=code_stats)

    root = get_byte_unit(dir_size(conf.root))
    temp = get_byte_unit(dir_size(conf.temp))
    logs = get_byte_unit(dir_size(conf.logs))
    dirs = f"Root: {root}\nTemp: {temp}\nLogs: {logs}"
    embed.add_field(name="Directory Info", value=dirs)

    conn = f"Connecting IP: {ip}\nHeartbeat Period: {latency} ms\nHeartbeat Frequency: {freq} Hz"
    embed.add_field("Connection Info", value=conn)
    return await ctx.respond(embed)


@bot.child()
@keikou.command("purge", "Purge all application commands. DANGEROUS.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def purge(ctx):
    """
    This is useful is some issue with slash commands occurs, but one should be
    aware that this command's execution tends to cause multiple validity errors
    with Discord gets the API all updated. As a result, the execution of this
    command is considered **DANGEROUS** and should only be used as a last resort.
    """
    msg = "You are about to purge all application commands. This action is **__DANGEROUS__** and can result in loss of functionality."
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    await menu.start((await resp.message()))
    await menu.wait_for_input()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])
    
    await ctx.bot.purge_application_commands(global_commands=True)
    return await ctx.respond("Purge completed, restart to re-register the commands.")


@admin.command()
@keikou.command("permissions", "Change, view, or edit permissions.")
@keikou.implements(keikou.SlashCommandGroup)
async def permissions(ctx):
    f"""
    {conf.name}'s permissions architecture lies at the core of the command handling system. While it is complex, it is founded upon only a few logical axioms. The permissions system relies on two concepts, *nodes* and *grant levels*.

    **Node**
    A node is simply a unique identifier attached to a command which allows it to be referenced uniquely, but heirarchially. A node is generally composed of the name of the plugin the command is in, followed by a dot, followed by the name of the command itself. For example, the node of the `/help` command that generated this message is `tools.help`, because it resides in the `tools` plugin, and the command's name is `help`.
    In previous versions of {conf.name}, that's all there was to it. However, slash commands allow for the creation of subgroups and subcommands which complicates nodes a bit more. If you have a command which is inside of a group, the node would be `plugin.group.command`. You can also have subgroups in groups. A command like that would have a node like so: `plugin.group.subgroup.command`. Thankfully, you aren't allowed to nest deeper than that, so that's as far as this goes.
    Some examples of this are commands like `/weather radiosonde`. In this case, the `/weather radiosonde` command is in the `weather` plugin, but it's also in a command group named `weather`. So the node of the `/weather radiosonde` command is `weather.weather.radiosonde`.

    **Grant Level**
    A grant level is a property attached to each command in {conf.name}'s source code. The grant level of each command effectively denotes the level of permission required to use the command. There are only two options for this, `explicit` and `implicit`:

    `explicit` - By default, __NO ONE__ can run explicit commands. To run such a command, you'd need to be *explicitly* allowed to run it.

    `implicit` - By default, __ANYONE__ can run implicit commands. One can be explicitly denied from using implicit commands, but by default, a person's permission to use it is *implied*.

    Let's look at an example, the `/bot kill` command. The `/bot kill` command has an `explicit` grant level. Makes sense, you probably don't want just anyone killing the bot. In order to run it, {conf.name} needs to be explicitly told who is allowed to run it. The node for `/bot kill` is `admin.bot.kill`. So to run it, their ACL would need to read `'admin.bot.kill': 'allow'`.

    **Wildcards**
    {conf.name} also supports wildcards in the ACL. Following the previous example, you could set someone's ACL to have `'admin.bot.kill': 'allow'` to let them run `/bot kill`. But you could also have `'admin.bot.*': 'allow'`. This would allow them to run not only `/bot kill`, but ***ANY*** command in the `/bot` command group.

    **Deny first**
    As a final note, {conf.name}'s permissions system works on a deny-first basis. This means that if any of a person's permissions deny them from using a command, they will not be allowed to use that command, period. This is true **EVEN IF** other parts of their ACL explicitly allow them to run the command.
    """
    pass


@permissions.child()
@keikou.option("role", "The role to manipulate.", type=hikari.Role, default=None)
@keikou.option("user", "The user to manipulate.", type=hikari.Member, default=None)
@keikou.option("value", "The value to set.", choices=["ALLOW", "DENY", "REMOVE"])
@keikou.option("node", "The node to modify.")
@keikou.command("set", "Set permissions for a user or role.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def set(ctx):
    f"""
    For more information on {conf.name}'s permissions system, see the `/help`
    topic on `/permissions`.
    """
    if ctx.options.user is None and ctx.options.role is None:
        return await ctx.respond("You must specify either a role or a user to modify.")
    if ctx.options.user is not None and ctx.options.role is not None:
        return await ctx.respond("You must select ONLY one user or one role, not both.")
    
    if ctx.options.node not in ctx.bot.permissions.nodes:
        return await ctx.respond(f"The specified node, `{ctx.options.node}` is not valid.")
    
    if ctx.options.user.id == ctx.bot.get_me().id:
        return await ctx.respond("Access is denied. I'll manage my own permissions, thanks.")
    
    if ctx.options.user is not None:
        name = ctx.options.user.username
        object, _ = await User.objects.aget_or_create(id=ctx.options.user.id)
    else:
        name = ctx.options.role.name
        object = await Role.objects.aget(id=ctx.options.role.id)
    
    if ctx.options.value == "REMOVE":
        try:
            po = await object.acl.aget(node=ctx.options.node)
        except PermissionsObject.DoesNotExist:
            return await ctx.respond(f"The node `{ctx.options.node}` was not found in the ACL for `{name}`.")
        await object.acl.aremove(po)
        await object.asave()
        return await ctx.respond(f"`{ctx.options.node}` removed from `{name}`'s ACL.")
    
    try:
        po = await object.acl.aget(node=ctx.options.node)
        if po.setting == ctx.options.value:
            return await ctx.respond(f"`{str(po)}` is already in `{name}`'s ACL.")
        
        await object.acl.aremove(po)
    except PermissionsObject.DoesNotExist:
        pass

    s = "-" if ctx.options.value == "DENY" else "+"
    po, _ = await PermissionsObject.objects.aget_or_create(node=ctx.options.node, setting=s)
    await po.asave()

    await object.acl.aadd(po)
    await object.asave()
    return await ctx.respond(f"`{str(po)}` was added to `{name}`'s ACL.")


@permissions.child()
@keikou.option("role", "The role to view.", type=hikari.Role, default=None)
@keikou.option("user", "The user to view.", type=hikari.Member, default=None)
@keikou.option("hide", "Whether or not the output should be hidden. True by default.", type=bool, default=True)
@keikou.command("acl", "Show the ACL for the specified user or role.")
@keikou.implements(keikou.SlashSubCommand)
async def acl(ctx):
    flags = hikari.MessageFlag.EPHEMERAL if ctx.options.hide is True else hikari.MessageFlag.NONE
    if ctx.options.user is None and ctx.options.role is None:
        obj, _ = await User.objects.aget_or_create(id=ctx.author.id)
        name = ctx.author.username
        pn = "their"
    elif ctx.options.user is not None and ctx.options.role is not None:
        return await ctx.respond("You must specify ONLY a user or a role, not both.")
    elif ctx.options.user is not None:
        obj, _ = await User.objects.aget_or_create(id=ctx.options.user.id)
        name = ctx.options.user.username
        pn = "their"
    elif ctx.options.role is not None:
        obj = await Role.objects.aget(id=ctx.options.role.id)
        name = ctx.options.role.name
        pn = "its"
    
    o_acl = ""
    async for o in obj.acl.all():
        o_acl += f"{o}\n"
    
    if o_acl == "":
        return await ctx.respond(f"`{name}` does not have anything in {pn} ACL.", flags=flags)
    return await ctx.respond(f"__{name}'s ACL__\n```{o_acl}```", flags=flags)


@admin.command()
@keikou.command("database", "Commands pertaining to database management.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashCommandGroup)
async def database(ctx):
    pass


@database.child()
@keikou.command("backup", "Create a backup of the existing database.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def backup(ctx):
    """
    Backs up the PostgreSQL database by dumping to a SQL file.
    """
    ctx.bot.logger.warning(f"Database backup call made by {ctx.author.username}.")

    # Ensure .pgpass file exists and is valid
    userpath = os.path.expanduser("~/")
    if not os.path.exists(os.path.join(userpath, ".pgpass")):
        with open(os.path.join(userpath, ".pgpass"), "w") as pgpassfile:
            pgpassfile.write(f"{conf.mvc.db_host}:{conf.mvc.db_port}:{conf.mvc.db_name}:{conf.mvc.db_user}:{conf.mvc.db_pass}")
        os.system(f"chmod 600 {os.path.join(userpath, '.pgpass')}")
    else:
        with open(os.path.join(userpath, ".pgpass"), "r") as pgpassfile:
            lines = pgpassfile.readlines()
        if f"{conf.mvc.db_host}:{conf.mvc.db_port}:{conf.mvc.db_name}:{conf.mvc.db_user}:{conf.mvc.db_pass}" not in lines:
            with open(os.path.join(userpath, ".pgpass"), "a") as pgpassfile:
                pgpassfile.write(f"{conf.mvc.db_host}:{conf.mvc.db_port}:{conf.mvc.db_name}:{conf.mvc.db_user}:{conf.mvc.db_pass}")

    os.system(f"pg_dump -U {conf.mvc.db_user} -h {conf.mvc.db_host} -p {conf.mvc.db_port} {conf.mvc.db_name} >> {os.path.join(conf.mvc.db_backup_dir, ctx.bot.localnow().strftime('database_backup_%Y_%m_%d_%H_%M_%S.sql'))}")
    return await ctx.respond("Database backup was successful.")      


def load(bot):
    bot.add_plugin(admin)


def unload(bot):
    bot.remove_plugin(admin)