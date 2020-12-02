"""
This module defines the bot's permissions system.

Similar to Minecraft permissions, each permission is defined with a node.
The node itself corresponds to a decorator above each command function.
These are usually done in a standard format, `cog_name.command_name`.
Whenever the command is run, the user's ACL is queried and checked for the node
corresponding to the command:

 - If the node is defined as DENY anywhere in the user's ACL, they are DENIED
   permission, regardless of any other permissions they have.
 - If the node is defined as ALLOW in the user's ACL, they are allowed, ONLY IF
   they are not DENIED elsewhere.
 - If the node is defined to require explicit permissions and is not present in
   user's ACL, they will be DENIED by default, unless they are explicitly allowed.
 - If the node is defined NOT to require explicit permissions, and is not
   present in the user's ACL, they will be allowed, UNLESS the node is denied
   explicitly elsewhere.

One final thing to note is that a special node exists, `bot.*`. If this node
is defined in a user's ACL as ALLOW, they are considered to have all permissions.
However, this does NOT override any nodes set to DENY. A deny will ALWAYS take
precedence over any allowed node.
"""

from libs.orm.member import Member

from discord.ext import commands

class Command(commands.Command):
    def __init__(self, func, **kwargs):
        super().__init__(func, **kwargs)
        self.grant_level = kwargs['grant_level'] if 'grant_level' in kwargs else 'implicit'
        self.add_check(self.permissions_check)

    def node(self, bot):
        for command in bot.commands:
            if command.qualified_name == self.qualified_name:
                return command.cog.qualified_name.lower() + "." + self.qualified_name.lower()

    def permissions_check(self, ctx):
        member = Member.obtain(ctx.author.id)
        cog, command = self.node(ctx.bot).split(".")

        # Check for explicit deny
        for node, value in member.acl.items():
            if (node == cog + "." + command) or (node == cog + ".*"):
                if value == "deny":
                    return False

        if self.grant_level != "implicit":
            for node, value in member.acl.items():
                if (node == cog + "." + command) or (node == cog + ".*"):
                    if value == "allow":
                        return True
                elif node == "bot.*":
                    if value == "allow":
                        return True
                else:
                    pass
            return False
        else:
            return True

def command(name=None, cls=None, **attrs):
    if cls is None:
        cls = Command

    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Callback is already a command.")
        return cls(func, name=name, **attrs)
    return decorator

def permission_exists(bot, node):
    if node == "bot.*":
        return True

    for cog in bot.cogs:
        if node == cog.lower() + ".*":
            return True

    for command in bot.commands:
        try:
            if command.node(bot) == node:
                return True
        except AttributeError:
            pass
    return False
