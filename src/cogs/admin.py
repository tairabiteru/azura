"""
Define the admin cog.

The admin cog contains commands which are both useful to server administrators
as well as the bot's maintainer.
"""

from core.conf import conf
from core.commands import SlashCommand, SlashCommandGroup, SlashSubCommand, SlashSubGroup
from core.commands import permission_exists, load_slash_commands, unload_slash_commands
from ext.utils import lint, localnow, strfdelta, reduceByteUnit, dirSize, getPublicIPAddr
from ext.ctx import Validation
from orm.revisioning import Revisioning
from orm.member import Member
from orm.server import Server as ServerORM


from lightbulb.slash_commands import Option
import hikari
import json
import typing


class Bot(SlashCommandGroup):
    description: str = f"Control {conf.name}."


@Bot.subcommand()
class Uptime(SlashSubCommand):
    description: str = f"View the current uptime of the {conf.name}."
    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           View {bot}'s current uptime.
           """

    async def callback(self, ctx):
        embed = hikari.embeds.Embed(title=f"{conf.name}'s Current Uptime")
        embed.add_field(name="Time Since Initialization", value=strfdelta((localnow() - ctx.bot.last_initalization), '{%H}:{%M}:{%S}'))
        embed.add_field(name="Time Since API Connection", value=strfdelta((localnow() - ctx.bot.last_api_connection), '{%H}:{%M}:{%S}'))
        await ctx.respond(embed)


@Bot.subcommand()
class Kill(SlashSubCommand):
    description: str = f"Kill the {conf.name} completely. This is irreversable."
    grant_level = "explicit"
    enabled_guilds = [294260795465007105, 320759902240899073]

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Stop {bot} cold. This command requires validation to complete. Once
           executed, its actions can only be reversed at the console.
           """

    choices = [conf.name]
    choices += list([f"AzuraChild-{i}" for i in range(0, len(conf.child_tokens))])
    choices.append("ALL")

    target: str = Option("The bots to issue the command to.", choices=choices)

    async def callback(self, ctx):
        msg = "You are about to issue a kill command. This action is **__IRREVERSABLE__** without console access!"
        async with Validation(ctx, msg) as validation:
            if validation is True:
                conf.logger.warning(f"Kill call by {ctx.author.username}. Proceeding with shutdown of target {ctx.options.target}...")
                if ctx.options.target in ["ALL", conf.name]:
                    await ctx.edit_response("🔌 Call to kill received. Shutting down now. Bye! 🔌", components=[])
                else:
                    await ctx.edit_response(f"🔌 Call to kill received. Shutting down {ctx.options.target}. 🔌", components=[])

                for child in ctx.bot.children:
                    if child.name == ctx.options.target or ctx.options.target == "ALL":
                        t = await child.kill()
                if ctx.options.target == conf.name or ctx.options.target == "ALL":
                    await ctx.bot.cycleState(kill=True)
            else:
                await ctx.edit_response("Action cancelled.", components=[])


@Bot.subcommand()
class StartChild(SlashSubCommand):
    description: str = f"Start a child of {conf.name}."
    enabled_guilds = [294260795465007105, 320759902240899073]
    grant_level = "explicit"

    choices = list([f"AzuraChild-{i}" for i in range(0, len(conf.child_tokens))])
    choices.append("ALL")
    target: str = Option("The bots to issue the command to.", choices=choices)

    async def callback(self, ctx):
        conf.logger.info(f"Init call by {ctx.author.username}. Proceeding with startup of target {ctx.options.target}...")
        msg = f"⚡ Initialization call made for target `{ctx.options.target}`. ⚡"
        await ctx.respond(msg)

        for child in ctx.bot.children:
            if child.name == ctx.options.target or ctx.options.target == "ALL":
                code = child.start()
                if code == 0:
                    msg += f"\n`{child.name}` initialized."
                else:
                    msg += f"\n`{child.name}` was already on."
                await ctx.edit_response(msg)


@Bot.subcommand()
class Reinitialize(SlashSubCommand):
    description: str = f"Restart {conf.name}."
    enabled_guilds = [294260795465007105, 320759902240899073]
    grant_level = "explicit"

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Restart {bot}. Before each reinitialization, {bot} will check over
           her current codebase with a linter to ensure that there are no errors.
           Optionally, you can `force` her to reinitialize, ignoring the linter.
           Doing this without knowing the nature of the errors can be dangerous,
           and prevent her from rebooting without console access.

           __**Options**__
           `[force]` - A boolean which determines if linting should take place
           or not. `False` means a check will take place, `True` means it won't.
           Defaults to `False`.
           """

    force: typing.Optional[bool] = Option("Reinitialize by force, ignoring the linter. Can be DANGEROUS.")

    choices = [conf.name]
    choices += list([f"AzuraChild-{i}" for i in range(0, len(conf.child_tokens))])
    choices.append("ALL")

    target: str = Option("The bots to issue the command to.", choices=choices)

    async def callback(self, ctx):
        if ctx.options.force is not True:
            await ctx.respond("🔍 Performing code inspection prior to reinitialization... 🔍")
            if errors := lint(conf.rootDir):
                plural = "error" if len(errors) == 1 else "errors"
                await ctx.edit_response(
                    f"__❌ Reinitialization call refused ❌__\n{len(errors)} {plural} in upstream code."
                )
                conf.logger.warning(
                    "Call to reinitialize failed due to the following errors in upstream code:"
                )
                for error in errors:
                    conf.logger.warning(
                        f"[{error['number']}] [{error['filename']}] [Line #{error['lnum']}] {error['text']}"
                    )
                return

        conf.logger.warning(f"Reinit call by {ctx.author.username}. Proceeding with shutdown of target {ctx.options.target}...")
        if ctx.options.target in ["ALL", conf.name]:
            if ctx.options.force is True:
                await ctx.respond("⚡ Use of force authorized. Reinitializing now. ⚡", components=[])
            else:
                await ctx.edit_response("⚡ Upstream code OK. Reinitializing now. ⚡", components=[])
            data = {"time": localnow().strftime("%x %X %z"), "channel": int(ctx.get_channel().id)}
            with open("reinit.json", "w") as file:
                json.dump(data, file, indent=4)
        else:
            if ctx.options.force is True:
                await ctx.respond(f"⚡ Use of force authorized. Reinitializing {ctx.options.target} now. ⚡", components=[])
            else:
                await ctx.edit_response(f"⚡ Upstream code OK. Reinitializing {ctx.options.target} now. ⚡", components=[])

        for child in ctx.bot.children:
            if child.name == ctx.options.target or ctx.options.target == "ALL":
                await child.reinit()
        if ctx.options.target == conf.name or ctx.options.target == "ALL":
            await ctx.bot.cycleState()


@Bot.subcommand()
class Tail(SlashSubCommand):
    description: str = "Show the last lines in the log. Defaults to the last 10."
    grant_level = "explicit"

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Read back console output. This is vital to troubleshooting, but the
           information provided by it isn't really useful to anyone but a developer.

           __**Options**__
           `[lines]` - The number of lines to show. Defaults to 10.
           `[containing]` - Allows a filter to be specified to search for certain lines.
           `[ephemeral]` - Whether or not response will be ephemeral. Defaults to True.
           """

    lines: typing.Optional[int] = Option("The number of lines to show.")
    containing: typing.Optional[str] = Option("Filter lines by what they contain.")
    ephemeral: typing.Optional[bool] = Option(
        "Should the response be hidden? Defaults to True."
    )

    async def callback(self, ctx):
        numlines = int(ctx.options.lines) if ctx.options.lines else 10
        flags = getEphemeralOrNone(ctx)
        with open("logs/bot.log", "r") as logfile:
            if ctx.options.containing is not None:
                lines = list(filter(lambda l: ctx.options.containing in l, logfile.readlines()))
            else:
                lines = logfile.readlines()
        lines = "".join(lines[-(numlines):]).replace("```", "'''")
        if len(lines) > 2000:
            await ctx.respond(
                "The number of lines requested exceeds 2,000 characters.", flags=flags
            )
            return
        await ctx.respond(f"```{lines}```", flags=flags)


@Bot.subcommand()
class Info(SlashSubCommand):
    description: str = f"Show information about {conf.name}."

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Display information about {bot}. This includes things like her
           version, the gateway latency, and the public IP address she's using,
           among other things.
           """

    async def callback(self, ctx):
        latency = round((ctx.bot.heartbeat_latency * 1000), 1)
        revisioning = Revisioning.obtain()
        embed = hikari.embeds.Embed(
            title=conf.name,
            url=conf.dash.outfacingURL,
            description=f"**Version {ctx.bot.version}**",
        )
        embed.set_thumbnail(ctx.bot.get_me().avatar_url)
        embed.add_field("Gateway Latency", value=f"{latency} ms")
        embed.add_field("Lines of Code", value="{:,}".format(revisioning.current.lines))
        embed.add_field(
            "Characters of Code", value="{:,}".format(revisioning.current.chars)
        )
        embed.add_field("Number of Commands", value=len(ctx.bot.commands))
        embed.add_field("Number of Slash Commands", value=len(ctx.bot.slash_commands))
        embed.add_field("Total Size", value=reduceByteUnit(dirSize(conf.rootDir)))
        embed.add_field(
            "Database Size", value=reduceByteUnit(dirSize(conf.orm.rootDir))
        )
        embed.add_field(
            "Temp Directory Size", value=reduceByteUnit(dirSize(conf.tempDir))
        )
        ip = await getPublicIPAddr()
        embed.add_field("Mainframe Public IP Address", value=ip)
        await ctx.respond(embed)


@Bot.subcommand()
class PurgeCommands(SlashSubCommand):
    description: str = "Purge all slash commands."
    grant_level = "explicit"

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Purges all of {bot}'s slash commands, forcing them to be re-added.
           Note that this command does not require validation, and its execution
           can have serious, if not temporary, ramifications. Use caution.
           """

    async def callback(self, ctx):
        await ctx.bot.purge_slash_commands(global_commands=True)
        await ctx.respond("Purge completed. Restart to re-register.")


class Permissions(SlashCommandGroup):
    description: str = "Change, view or check bot permissions."

    help = f"""
           {conf.name}'s permissions architecture lies at the core of the command handling system. While it is complex, it is founded on only a few logical axioms. The permissions system relies on two concepts, *nodes* and *grant levels*.

           **Node**
           A node is simply a unique identifier attached to a command which allows it to be referenced uniquely, but heirarchially. A node is generally composed of the name of the cog the command is in, followed by a dot, followed by the name of the command itself. For example, the node of the `/help` command that generated this message is `tools.help`, because it resides in the `tools` cog, and the command's name is `help`.
           In previous versions of {conf.name}, that's all there was to it. However, slash commands allow for the creation of subgroups and subcommands which complicates nodes a bit more. If you have a command which is inside of a group, the node would be `cog.group.command`. You can also have subgroups in groups. A command like that would have a node like so: `cog.group.subgroup.command`. Thankfully, you aren't allowed to nest deeper than that, so that's as far as this goes.
           Some examples of this are commands like `/weather radiosonde`. In this case, the `/weather radiosonde` command is in the `weather` cog, but it's also in a command group named `weather`. So the node of the `/weather radiosonde` command is `weather.weather.radiosonde`.

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


@Permissions.subcommand()
class Set(SlashSubCommand):
    description: str = "Set permissions for a user or role."
    grant_level = "explicit"

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Sets a permissions node for a user or role. Permissions are complicated
           and nuanced, so if you want to know more, you should run `/help permissions`.

           __**Options**__
           `<object>` - The object to modify. This is a mentionable like a @member
           or @role.
           `<permissions_node>` - The permissions node to modify.
           `<value>` - The value to set the node to, either `allow` or `deny`.
           You can also specify `remove` to simply remove the node from the ACL.
           """

    object: hikari.Snowflake = Option("The user or role to set permissions for.")
    permissions_node: str = Option("The permissions node to set.", name="node")
    value: str = Option("The value to set the permissions node to.")

    async def callback(self, ctx):
        object = resolve(ctx, "object")
        if object.id == ctx.bot.get_me().id:
            return await ctx.respond(
                "Access is denied. I'll manage my own permissions, thanks."
            )
        if ctx.options.value not in ["allow", "deny", "remove"]:
            return await ctx.respond(
                f"Invalid value `{ctx.options.value}`. Must be one of `allow`, `deny` or `remove`."
            )
        if not permission_exists(ctx.bot, ctx.options.node):
            return await ctx.respond(
                f"Invalid permissions node `{ctx.options.node}`."
            )

        if isinstance(object, hikari.users.UserImpl):
            orm_object = Member.obtain(object.id)
            name = object.username
            args = []
        elif isinstance(object, hikari.guilds.Role):
            server = ServerORM.obtain(object.guild_id)
            orm_object = server.get_role(object.id)
            name = object.name
            args = [server]
        else:
            raise ValueError(f"Invalid permissions object: {object}.")

        if ctx.options.value == "remove":
            try:
                orm_object.acl.pop(ctx.options.node)
                orm_object.save()
                return await ctx.respond(
                    f"`{ctx.options.node}` removed from ACL for `{name}`."
                )
            except KeyError:
                return await ctx.respond(
                    f"`{ctx.options.node}` not found in ACL for `{name}`."
                )

        for node, value in orm_object.acl.items():
            if node == ctx.options.node:
                if value == ctx.options.value:
                    return await ctx.respond(
                        f"`{node}` is already set to `{value}` for `{name}`."
                    )

        orm_object.acl[ctx.options.node] = ctx.options.value
        orm_object.save(*args)

        await ctx.respond(
            f"`{ctx.options.node}` set to `{ctx.options.value}` for `{name}`."
        )


@Permissions.subcommand()
class Show(SlashSubCommand):
    description: str = "Show the ACL for the specified user. Defaults to the author."

    help = """
           Syntax: `{pre}{name}`

           **Node:** `{node}`
           **Grant Level:** `{grant_level}`

           __**Description**__
           Show the specified object's ACL. If no user is specified, it defaults to the author.

           __**Options**__
           `[object]` - The object to view. This is a mentionable like a @member
           or @role. If not specified, it defaults to the author.
           `[ephemeral]` - Whether or not the response should be ephemeral. Defaults to True.
           """

    object: typing.Optional[hikari.User] = Option(
        "The user or role whose ACL you wish to see. Defaults to the author."
    )
    ephemeral: typing.Optional[bool] = Option(
        "Whether or not the response should be ephemeral. Defaults to True."
    )

    async def callback(self, ctx):
        if ctx.options.object is not None:
            object = resolve(ctx, "object")
        else:
            object = ctx.author
        flags = getEphemeralOrNone(ctx)

        if isinstance(object, hikari.users.UserImpl):
            orm_object = Member.obtain(object.id)
        elif isinstance(object, hikari.guilds.Role):
            orm_object = ServerORM.obtain(object.guild_id).get_role(object.id)
        msg = ""
        for node, value in orm_object.acl.items():
            msg += f"{node}: {value}\n"
        await ctx.respond(f"```JSON\n{msg}```", flags=flags)


def load(bot):
    load_slash_commands(bot)


def unload(bot):
    unload_slash_commands(bot)
