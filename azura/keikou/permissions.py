from core.conf import conf

import enum
import lightbulb

import orm.models as models


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


def check_acl(command, acl):
    node_pieces = command.node.split(".")

    current = node_pieces[0]
    for node_piece in node_pieces[1:]:
        for node, value in acl.items():
            if (node == f"{current}.{node_piece}") or (node == f"{current}.*"):
                if value == "deny":
                    return PermissionCheckResult(command, "explicit deny")
            elif node == "*":
                if value == "deny":
                    return "explicit deny"
        current = f"{current}.{node_piece}"

    if command.grant_level != GrantLevel.IMPLICIT:
        current = node_pieces[0]
        for node_piece in node_pieces[1:]:
            for node, value in acl.items():
                if (node == f"{current}.{node_piece}") or (node == f"{current}.*"):
                    if value == "allow":
                        return PermissionCheckResult(command, "explicit allow")
                elif node == "*":
                    if value == "allow":
                        return PermissionCheckResult(command, "explicit allow")
        return PermissionCheckResult(command, "implicit deny")
    else:
        return PermissionCheckResult(command, "implicit allow")


def evaluate_permissions(user, roledatums, command):
    master_acl = {user.hikari_user.id: check_acl(command, user.acl)}

    for role in roledatums:
        master_acl[role.hikari_role.id] = check_acl(command, role.acl)

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
    if ctx.member.user.id == conf.owner_id:
        return True

    user = await models.User.get_or_create(ctx.member.user)
    roledatums = await models.RoleDatum.get_roles_for_member(ctx.member.user, ctx.get_guild())
    object, check = evaluate_permissions(user, roledatums, ctx.invoked)

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
