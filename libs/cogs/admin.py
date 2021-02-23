"""Admin module containing administrative commands."""

from libs.ext.utils import localnow, strfdelta, Validation, human_bytes
from libs.core.permissions import command, permission_exists
from libs.core.conf import conf
from libs.core.log import logprint
from libs.core.azura import revisionCalc
from libs.orm.revisioning import Revisioning
from libs.orm.uptime import UptimeRecords
from libs.orm.member import Member

import discord
from discord.ext import commands
import os
import pickle
import pyfiglet


class Admin(commands.Cog):
    """Admin Cog containing administrative commands."""

    def __init__(self, bot):
        """Initialize Cog."""
        self.bot = bot

    @command(grant_level="explicit", aliases=['reinit'])
    async def restart(self, ctx, module="bot"):
        """
        Syntax: `{pre}{command_name} [module]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Reinitializes the specified module. If no module is specified, the
        entire bot will be reinitialized.

        __**Arguments**__
        `[module]` - The module to reinitialize. If no module is specified, the
        entire bot will be reinitialized.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} admin`
        """
        if module == "bot":
            async with ctx.typing():
                logprint("Restart called by {user}. Preparing for reinitialization...".format(user=ctx.author.name), type="warn")
                await ctx.send("⚡ Preparing for reinitialization ⚡")
                pickle.dump(ctx.channel.id, open("restart.init", "wb"))
                logprint("...reinitializing now!", type="warn")
                await self.bot.logout()
                await self.bot.close()
        else:
            for mod in self.bot.extensions:
                if module == mod.split(".")[-1]:
                    self.bot.reload_extension(mod)
                    rev, logoutput = revisionCalc()
                    if not self.bot.revised and str(rev.current) != str(self.bot.revision.current):
                        logprint("Code has been revised since last initialization.", type="warn")
                        self.bot.revised = True
                    return await ctx.send("`{cog}` reloaded.".format(cog=mod.split(".")[-1]))
            else:
                return await ctx.send("No cog named `{cog}` exists.".format(cog=mod.split(".")[-1]))

    @command(grant_level="explicit")
    async def kill(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Kills {bot} dead. Upon usage, {bot} will ask you to confirm your
        action by entering a hash. If the hash is successfully completed, {bot}
        will shut down.
        __**!!! WARNING !!!**__
        Using this command will **IRREVERSABLY** stop {bot}. The __ONLY__ way
        to restart {bot} after running this command is via the console!

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        warn = "__**!!! WARNING !!!**__\nKilling {name} is **IRREVERSABLE** without direct server console access! \
         There is __NO WAY__ to restart after a kill command without direct access to the server terminal!".format(name=conf.name)
        async with Validation(ctx, warn) as validation:
            if validation:
                logprint("Kill called by {user}. Proceeding with shutdown...".format(user=ctx.author.name), type="warn")
                await ctx.send("🔌 Kill signal recieved. Shutting down now...🔌")
                os.system("touch {file}".format(file=os.path.join(conf.rootDir, "lock")))
                await ctx.send("Goodbye!")
                await self.bot.logout()
                await self.bot.close()

    @command(grant_level="explicit")
    async def leave(self, ctx, server_id: int):
        """
        Syntax: `{pre}{command_name} <server_id>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Causes {bot} to leave the server specified by the server ID.

        __**Arguments**__
        `<server_id>` - The ID of the server {bot} should leave.

        __**Example Usage**__
        `{pre}{command_name} 123456789012345678`
        """
        server = self.bot.get_guild(server_id)
        await server.leave()
        return await ctx.send("Left {server}".format(server=server.name))

    @command(grant_level="explicit", aliases=["dis"])
    async def disable(self, ctx, command_name):
        """
        Syntax: `{pre}{command_name} <command_name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Disables the command with the specified name.

        __**Arguments**__
        `<command_name>` - The name of the command to disable.

        __**Example Usage**__
        `{pre}{command_name} say`
        """
        command = self.bot.get_command(command_name)
        if not command:
            return await ctx.send("A command by the name \"{command}\" does not exist.".format(command=command_name))
        elif command.qualified_name == "disable":
            return await ctx.send("You can't disable `/disable`.")
        elif command.qualified_name == "enable":
            return await ctx.send("You can't disable `/enable`")
        elif not command.enabled:
            return await ctx.send("`/{command}` command is already disabled.".format(command=command.qualified_name))
        else:
            command.enabled = False
            return await ctx.send("`/{command}` is now disabled.".format(command=command.qualified_name))

    @command(grant_level="explicit", aliases=['en'])
    async def enable(self, ctx, command_name):
        """
        Syntax: `{pre}{command_name} <command_name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enables the command with the specified name.

        __**Arguments**__
        `<command_name>` - The name of the command to enable.

        __**Example Usage**__
        `{pre}{command_name} say`
        """
        command = self.bot.get_command(command_name)
        if not command:
            return await ctx.send("A command by the name \"{command}\" does not exist.".format(command=command_name))
        elif command.enabled:
            return await ctx.send("`/{command}` command isn't disabled.".format(command=command.qualified_name))
        else:
            command.enabled = True
            return await ctx.send("`/{command}` is now enabled.".format(command=command.qualified_name))

    @command(aliases=["lsdisabled", "lsdis", 'listdisabled'])
    async def list_disabled(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        List all of the currently disabled commands.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        disabled_commands = list([command for command in self.bot.commands if not command.enabled])
        if len(disabled_commands) == 0:
            return await ctx.send("No commands are currently disabled.")
        else:
            msg = "The following commands are currently disabled:\n"
            for command in disabled_commands:
                msg += "`/{command}`, ".format(command=command.qualified_name)
            msg = msg[:-2]
            return await ctx.send(msg)

    @command(aliases=['info', 'about', 'codebase', 'version'])
    async def information(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Displays various metrics about {bot}.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        revisioning = Revisioning.obtain()
        banner = pyfiglet.Figlet(font="slant")
        embed = discord.Embed(title="Wiki Page",
                              colour=discord.Colour(0x2fff58),
                              url=conf.dash.outfacingURL,
                              description="```" + banner.renderText(conf.name) + "```\n" + "**Version ** " + str(revisioning.current))
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        embed.add_field(name="Cogs", value="{:,}".format(len(self.bot.cogs)))
        embed.add_field(name="Commands", value="{:,}".format(len(self.bot.commands)))
        embed.add_field(name="Files", value="{:,}".format(revisioning.current.files))
        embed.add_field(name="Total size", value="{:,}".format(revisioning.current.size) + " bytes")
        embed.add_field(name="Lines of Code", value="{:,}".format(revisioning.current.lines))
        embed.add_field(name="Characters of Code", value="{:,}".format(revisioning.current.chars))
        return await ctx.send(embed=embed)

    @command(aliases=['ut'])
    async def uptime(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Display {bot}'s current uptime statistics.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        uptimes = UptimeRecords.obtain()
        ut = uptimes.total_uptime
        dt = uptimes.total_downtime
        utpercent = uptimes.percentage_up
        dtpercent = uptimes.percentage_down
        embed = discord.Embed(title=f"__**{conf.name} Uptime Statistics**__", color=discord.Colour(0xd9e0cf), description="As of " + localnow().strftime("%-m/%-d/%Y %H:%M:%S %Z"))
        embed.add_field(name="Total Uptime", value=strfdelta(ut, "{%d} days {%H}:{%M}:{%S}\n") + " (" + str(round(utpercent, 2)) + "%)")
        embed.add_field(name="Total Downtime", value=strfdelta(dt, "{%d} days {%H}:{%M}:{%S}\n") + " (" + str(round(dtpercent, 2)) + "%)")
        embed.add_field(name="Current Session", value=strfdelta(localnow() - uptimes.current_uptime.start_timestamp, "{%d} days {%H}:{%M}:{%S}"))
        embed.add_field(name="Initialization Instances", value="{:,}".format(len(uptimes.all) + 1))
        await ctx.send(embed=embed)

    @command(aliases=['listpermissions', 'listperm', 'lsperm', 'lspermissions', 'acl'])
    async def check_permissions(self, ctx, member: discord.Member = None):
        """
        Syntax: `{pre}{command_name} [@Member]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Display the permissions list of the specified member. If no member is
        specified, it defaults to the author.

        __**Arguments**__
        `[@Member]` - The member whose permissions you want to see. If no
        member is specified, it defaults to the author.

        __**Example Usage**__
        `{pre}{command_name} @Taira`
        """
        if member is None:
            member = ctx.author
        memberobj = Member.obtain(member.id)
        if not memberobj.acl:
            return await ctx.send("{user} has nothing in their ACL.".format(user=member.name))
        out = "__{user}'s ACL__\n```".format(user=member.name)
        for perm_node, value in memberobj.acl.items():
            out += "'{node}': {value}\n".format(node=perm_node, value=value)
        return await ctx.send(out + "```")

    @command(grant_level="explicit", aliases=['setpermissions', 'setperm', 'permset'])
    async def set_permissions(self, ctx, member: discord.Member = None, node=None, value=None):
        """
        Syntax: `{pre}{command_name} <@Member> <node> <value>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Set permissions for the specified member at the specified node to the
        specified value.

        Permissions nodes for a given command are the name of the cog the
        command belongs to, followed by the non-alias name of the command itself
        in all lowercase letters. For example, this command belongs to the `Admin`
        cog, and is named `set_permissions`, so the node would be `admin.set_permissions`.

        {bot}'s permissions work on a deny-first basis. This means that if a
        member is denied permission for a command **anywhere** in their ACL, they
        will be unable to use that command, even if it is allowed elsewhere.

        By default, all commands are allowed to be run by anyone, except those
        commands whose grant level is set to `explicit`. Explicit grant level
        commands can only be run by those who have the node for the command
        explicitly set to `allow`. `remove`ing a node from a user's ACL will set
        the behavior of the command back to the default.

        Further, you can specify a wildcard by adding `.*` to the end of a cog.
        `admin.*` for example references all commands in the `Admin` cog. Finally,
        a special node exists, `bot.*` which references all commands, period.

        __**Arguments**__
        `<@Member>` - The member whose ACL you want to alter.
        `<node>` - The node in the member's ACL you want to set.
        `value` - The value to set the node to. Must be one of `allow`, `deny`,
        or `remove`.

        __**Example Usage**__
        `{pre}{command_name} @Taira bot.* allow`
        `{pre}{command_name} @Azura admin.restart deny`
        `{pre}{command_name} @Taira weather.* remove`
        """
        if member is None:
            return await ctx.send("You must specify the user whose permissions you want to change.")
        if member.id == self.bot.user.id:
            return await ctx.send("Access is denied. I'll manage my own permissions, thank you very much.")
        if node is None:
            return await ctx.send("You must specify the node you want to modify.")
        if value is None:
            return await ctx.send("You must specify what value to set the node to.")
        if value not in ['allow', 'deny', 'remove']:
            return await ctx.send("Invalid value `{value}`. It must be `allow`, `deny`, or `remove`.")
        if not permission_exists(self.bot, node):
            return await ctx.send("Invalid permissions node `{node}`. Permissions nodes follow the format `cog.command` or `cog.*` for all commands in a cog.".format(node=node))
        member_o = Member.obtain(member.id)
        if value == "remove":
            try:
                member_o.acl.pop(node)
                member_o.save()
                return await ctx.send("`{node}` removed from ACL for {user}.".format(node=node, user=member.name))
            except KeyError:
                return await ctx.send("`{node}` not found in ACL for {user}.".format(node=node, user=member.name))
        for n, val in member_o.acl.items():
            if n == node:
                if val == value:
                    return await ctx.send("`{node}` is already set to `{value}` for {user}.".format(node=node, value=value, user=member.name))
        member_o.acl[node] = value
        member_o.save()
        return await ctx.send("`{node}` set to `{value}` for {user}.".format(node=node, value=value, user=member.name))


def setup(bot):
    """Set up cog."""
    bot.add_cog(Admin(bot))
