"""Module defining Keikou's permission system

Keikou's permission system is actually based on Minecraft permissions, believe it or not.
The concept at work here is that commands possess a property called a "node". The node of
a command is calculated automatically based upon its position in the entire ecosystem.
As an example, take the /delete command. This command is located in the admin plugin, so
the node would be 'admin.delete'.
Similarly, take the /weather radiosonde command. It is located in the weather plugin, and
the radiosonde command itself is a subcommand of the larger /weather command, so its node
would be 'weather.weather.radiosonde'.

Nodes can also be wildcards. For example, the node 'admin.*' refers to all commands in the
admin plugin. Similarly, 'admin.permissions.*' refers to all subcommands under the /permissions
command.

Finally, a command is hard coded to require an either EXPLICIT or IMPLICIT grant level.
Keikou will permit the execution of commands with an IMPLICIT grant level as long as the
executor's ACL does not explicitly forbid them from executing it.
Likewise, Keikou will DENY the execution of commands with an EXPLICIT grant level unless
their ACL explicitly ALLOWs them to do it.

    * GrantLevel - Enum defining EXPLICIT and IMPLICIT grant levels
    * EXPLICIT - Shortcut to GrantLevel.EXPLICIT
    * IMPLICIT - Shortcut to GrantLevel.IMPLICIT

    * PermissionCheck - Class subclassing a Lightbulb check defining the check callbacks for all Keikou commands
    * CheckFailure - Error thrown when a permissions check fails within Keikou
    * PermissionCheckResult - Class whose object is returned from a permissions check
    * check_acl - Function which evaluates the passed ACL against the passed command to determine if it can be run
    * evaluate_permissions - Function which abstracts the functionality of the previous function to take a user and their roles
    * evaluate_permissions_for_check - Does the same as the above function, but throws a CheckFailure if it fails
    * PermissionsManager - Class whose object is instantiated alongside the bot to allow for global reading of the permissions system
"""


import enum
import lightbulb

from ..mvc.discord.models import User, Role


class GrantLevel(enum.Enum):
    EXPLICIT = "EXPLICIT"
    IMPLICIT = "IMPLICIT"


EXPLICIT = GrantLevel.EXPLICIT
IMPLICIT = GrantLevel.IMPLICIT


class PermissionCheck(lightbulb.checks.Check):
    def __init__(self, command, *args, **kwargs):
        self.command = command
        super().__init__(
            p_callback=evaluate_permissions_for_check,
            s_callback=evaluate_permissions_for_check,
        )


class CheckFailure(lightbulb.CheckFailure):
    def __init__(self, ctx, check):
        super().__init__()
        self.ctx = ctx
        self.check = check

        self.verbose_reason = f"Check failure occurred for {ctx.author.username} ({ctx.author.id}) for command {self.check.command.name} ({self.check.command.node}) with result '{self.check.result}'."

        if "explicit" in self.check.result:
            self.reason = f"Access is denied. Your ACL explicitly denies the use of `{self.check.command.name}`. (`{self.check.command.node}`)."
        else:
            self.reason = f"Access is denied. The use of `{self.check.command.name}` requires the node `{self.check.command.node}` to be explicitly allowed."

    async def send_response(self):
        await self.ctx.respond(self.reason)


class PermissionCheckResult:
    def __init__(self, command, result):
        self.command = command
        self.result = result

    @property
    def allowed(self):
        return "deny" not in self.result
    
    def __repr__(self):
        return f"{self.command}: {self.result}"


def check_acl(command, acl):
    node_pieces = command.node.split(".")
    current = node_pieces[0]
    for node_piece in node_pieces[1:]:
        for node, value in acl.items():
            if (node == f"{current}.{node_piece}") or (node == f"{current}.*"):
                print()
                if value == "-":
                    return PermissionCheckResult(command, "explicit deny")
            elif node == "*":
                if value == "-":
                    return "explicit deny"
        current = f"{current}.{node_piece}"

    if command.grant_level != GrantLevel.IMPLICIT:
        current = node_pieces[0]
        for node_piece in node_pieces[1:]:
            for node, value in acl.items():
                if (node == f"{current}.{node_piece}") or (node == f"{current}.*"):
                    if value == "+":
                        return PermissionCheckResult(command, "explicit allow")
                elif node == "*":
                    if value == "+":
                        return PermissionCheckResult(command, "explicit allow")
            current = f"{current}.{node_piece}"
        return PermissionCheckResult(command, "implicit deny")
    else:
        return PermissionCheckResult(command, "implicit allow")


async def evaluate_permissions(user, roles, command):
    user_acl = await user.fetch_acl()
    master_acl = {user.id: check_acl(command, user_acl)}

    async for role in roles:
        role_acl = await role.fetch_acl()
        master_acl[role.id] = check_acl(command, role_acl)

    for possible_result in [
        "explicit deny",
        "explicit allow",
        "implicit deny",
        "implicit allow",
    ]:
        for object, check in master_acl.items():
            if check.result == possible_result:
                return (object, check)


async def evaluate_permissions_for_check(ctx):
    user, _ = await User.objects.aget_or_create(id=ctx.member.user.id)
    roles = Role.objects.filter(id__in=ctx.member.role_ids)
    object, check = await evaluate_permissions(user, roles, ctx.invoked)
    if not check.allowed:
        raise CheckFailure(ctx, check)

    return True


class PermissionsManager:
    def __init__(self, bot):
        self.bot = bot

    def getCommandObjectByNode(self, node):
        for plugin in self.bot.plugins.values():
            if plugin.node == node:
                return plugin
            for command in plugin.all_commands:
                if command.node == node:
                    return command
                if hasattr(command, "subcommands"):
                    for subcommand in command.subcommands.values():
                        if subcommand.node == node:
                            return subcommand
                        if hasattr(subcommand, "subcommands"):
                            for subsubcommand in subcommand.subcommands.values():
                                if subsubcommand.node == node:
                                    return subsubcommand

    @property
    def nodes(self):
        nodes = ["*"]
        for plugin in self.bot.plugins.values():
            nodes.append(f"{plugin.node}.*")
            for command in plugin.all_commands:
                if not hasattr(command, "subcommands"):
                    nodes.append(command.node)
                else:
                    nodes.append(f"{command.node}.*")
                    for subcommand in command.subcommands.values():
                        if not hasattr(subcommand, "subcommands"):
                            nodes.append(subcommand.node)
                        else:
                            nodes.append(f"{subcommand.node}.*")
                            for subsubcommand in subcommand.subcommands.values():
                                nodes.append(subsubcommand.node)
        return nodes
