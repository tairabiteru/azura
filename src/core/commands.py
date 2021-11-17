from core.conf import conf
from orm.member import Member
from orm.server import Server

import abc
import collections
import inspect
from lightbulb import command_handler
from lightbulb.slash_commands import SlashCommand as LightbulbSlashCommand
from lightbulb.slash_commands import SlashCommandGroup as LightbulbSlashCommandGroup
from lightbulb.slash_commands import SlashSubGroup as LightbulbSlashSubGroup
from lightbulb.slash_commands import SlashSubCommand as LightbulbSlashSubCommand
from lightbulb.errors import CheckFailure
import sys
import typing


class SlashCommandCheckFailure(CheckFailure):
    def __init__(self, ctx, check):
        super().__init__()
        self.ctx = ctx
        self.check = check

        self.verbose_reason = f"Check failure occurred for {ctx.author.username} ({ctx.author.id}) for command {self.check.command.name} ({self.check.command.node}) with result '{self.check.result}'."

        if "explicit" in self.check.result:
            self.reason = f"Access is denied. The ACL explicitly denies the use of `{self.check.command.name}` (`{self.check.command.node}`)."
        else:
            self.reason = f"Access is denied. The use of `{self.check.command.name}` requires the node `{self.check.command.node}` to be explicitly allowed."
        conf.logger.debug(self.verbose_reason)

    async def send_response(self):
        await self.ctx.respond(self.reason)


class PermissionsCheck:
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
                    return PermissionsCheck(command, "explicit deny")
            elif node == "bot.*":
                if value == "deny":
                    return "explicit deny"
        current = f"{current}.{node_piece}"

    if command._grant_level != "implicit":
        current = node_pieces[0]
        for node_piece in node_pieces[1:]:
            for node, value in acl.items():
                if (node == f"{current}.{node_piece}") or (node == f"{current}.*"):
                    if value == "allow":
                        return PermissionsCheck(command, "explicit allow")
                elif node == "bot.*":
                    if value == "allow":
                        return PermissionsCheck(command, "explicit allow")
        return PermissionsCheck(command, "implicit deny")
    else:
        return PermissionsCheck(command, "implicit allow")


def evaluate_permissions(executor, guild, command):
    roles = executor.get_roles()
    executor = Member.obtain(executor.id)
    server = Server.obtain(guild.id)

    master_acl = {executor: check_acl(command, executor.acl)}

    for role in roles:
        role_orm = server.get_role(role.id)
        if role_orm:
            try:
                master_acl[role] = check_acl(command, role_orm.acl)
            except AttributeError:
                pass

    for possible_result in [
        "explicit deny",
        "explicit allow",
        "implicit deny",
        "implicit allow",
    ]:
        for object, check in master_acl.items():
            if check.result == possible_result:
                return (object, check)


def with_permission(command):
    async def decorator(*args, **kwargs):
        ctx = args[0]
        object, check = evaluate_permissions(ctx.member, ctx.get_guild(), command)
        if not check.allowed:
            raise SlashCommandCheckFailure(ctx, check)

        conf.logger.debug(
            f"Executing {command.node} for {ctx.author.username} ({ctx.author.id})."
        )
        await command.callback(*args, **kwargs)

        conf.logger.debug(
            f"Execution of {command.node} completed for {ctx.author.username} ({ctx.author.id})."
        )

    return decorator


def permission_exists(bot, node):
    if node == "bot.*":
        return True

    for command in bot.slash_commands:
        if isinstance(command, SlashCommand):
            if command.node == node or f"{command.parentNode}.*" == node:
                return True
        elif isinstance(command, SlashCommandGroup):
            if command.node == node or f"{command.parentNode}.*" == node:
                return True
            for subcommand in command._subcommands.values():
                if isinstance(subcommand, SlashSubCommand):
                    if subcommand.node == node or f"{subcommand.parentNode}.*" == node:
                        return True
                if isinstance(subcommand, SlashSubGroup):
                    for subsubcommand in subcommand._subcommands.values():
                        if isinstance(subsubcommand, SlashSubCommand):
                            if (
                                subsubcommand.node == node
                                or f"{subsubcommand.parentNode}.*" == node
                            ):
                                return True
                        else:
                            raise ValueError(
                                f"Invalid type found: {type(subsubcommand)} for {subsubcommand}."
                            )
    return False


class SlashCommand(LightbulbSlashCommand, abc.ABC):
    @property
    def enabled_guilds(self):
        return None

    @classmethod
    def getNode(cls):
        cog = cls.getParentNode()
        cmd = cls.__name__.lower()
        return f"{cog}.{cmd}"

    @classmethod
    def getParentNode(cls):
        cog = inspect.getmodule(cls).__name__.lower()
        cog = cog.split(".")[-1]
        return cog

    @property
    def node(self) -> str:
        return self.__class__.getNode()

    @property
    def parentNode(self) -> str:
        return self.__class__.getParentNode()

    @property
    @abc.abstractmethod
    def description(self) -> str:
        ...

    @property
    def _grant_level(self) -> str:
        try:
            return self.grant_level
        except AttributeError:
            return "implicit"

    async def __call__(self, *args, **kwargs):
        return await with_permission(self)(*args, **kwargs)


class SlashSubCommand(LightbulbSlashSubCommand, abc.ABC):
    @property
    def enabled_guilds(self):
        return None

    @property
    @abc.abstractmethod
    def description(self) -> str:
        ...

    @property
    def _grant_level(self) -> str:
        try:
            return self.grant_level
        except AttributeError:
            return "implicit"

    async def __call__(self, *args, **kwargs):
        return await with_permission(self)(*args, **kwargs)


class SlashSubGroup(LightbulbSlashSubGroup, abc.ABC):

    _subcommand_dict: typing.Dict[
        str, typing.List[typing.Type[SlashSubCommand]]
    ] = collections.defaultdict(list)

    def __init__(self, bot: command_handler.Bot):
        super().__init__(bot)
        self._subcommands: typing.MutableMapping[str, SlashSubCommand] = {}
        for cmd_class in self._subcommand_dict.get(self.__class__.__name__.lower(), []):
            cmd = cmd_class(bot)
            self._subcommands[cmd.name] = cmd

    @property
    def enabled_guilds(self):
        return None

    @classmethod
    def subcommand(
        cls,
    ) -> typing.Callable[[typing.Type[SlashSubCommand]], typing.Type[SlashSubCommand]]:
        def decorate(
            subcommand_class: typing.Type[SlashSubCommand],
        ) -> typing.Type[SlashSubCommand]:
            subcommand_class.parentNode = f"{cls.node}"
            subcommand_class.node = f"{cls.node}.{subcommand_class.__name__.lower()}"
            cls._subcommand_dict[cls.__name__.lower()].append(subcommand_class)
            return subcommand_class

        return decorate


class SlashCommandGroup(LightbulbSlashCommandGroup, abc.ABC):

    _subcommand_dict: typing.Dict[
        str,
        typing.List[
            typing.Union[typing.Type[SlashSubCommand], typing.Type[SlashSubGroup]]
        ],
    ] = collections.defaultdict(list)

    def __init__(self, bot: command_handler.Bot):
        super().__init__(bot)
        self._subcommands: typing.MutableMapping[str, SlashSubCommand] = {}
        for cmd_class in self._subcommand_dict.get(self.__class__.__name__.lower(), []):
            cmd = cmd_class(bot)
            self._subcommands[cmd.name] = cmd

    @classmethod
    def subcommand(
        cls,
    ) -> typing.Callable[[typing.Type[SlashSubCommand]], typing.Type[SlashSubCommand]]:
        def decorate(
            subcommand_class: typing.Type[SlashSubCommand],
        ) -> typing.Type[SlashSubCommand]:
            subcommand_class.parentNode = f"{cls.getNode()}"
            subcommand_class.node = (
                f"{cls.getNode()}.{subcommand_class.__name__.lower()}"
            )
            cls._subcommand_dict[cls.__name__.lower()].append(subcommand_class)
            return subcommand_class

        return decorate

    @classmethod
    def subgroup(
        cls,
    ) -> typing.Callable[[typing.Type[SlashSubGroup]], typing.Type[SlashSubGroup]]:
        def decorate(
            subgroup_class: typing.Type[SlashSubGroup],
        ) -> typing.Type[SlashSubGroup]:
            subgroup_class.parentNode = f"{cls.getNode()}"
            subgroup_class.node = f"{cls.getNode()}.{subgroup_class.__name__.lower()}"
            cls._subcommand_dict[cls.__name__.lower()].append(subgroup_class)
            return subgroup_class

        return decorate

    @classmethod
    def getNode(cls):
        cog = cls.getParentNode()
        cmd = cls.__name__.lower()
        return f"{cog}.{cmd}"

    @classmethod
    def getParentNode(cls):
        cog = inspect.getmodule(cls).__name__.lower()
        cog = cog.split(".")[-1]
        return cog

    @property
    def node(self) -> str:
        return self.__class__.getNode()

    @property
    def parentNode(self) -> str:
        return self.__class__.getParentNode()

    @property
    def _grant_level(self) -> str:
        try:
            return self.grant_level
        except AttributeError:
            return "implicit"

    @property
    def enabled_guilds(self):
        return None


CMDGROUPS = [SlashCommand, SlashCommandGroup]


def load_slash_commands(bot):
    module = inspect.getmodule(inspect.stack()[1][0])
    for name, cls in inspect.getmembers(sys.modules[module.__name__], inspect.isclass):
        if any([issubclass(cls, slashclass) for slashclass in CMDGROUPS]):
            if cls in CMDGROUPS:
                continue
            bot.add_slash_command(cls)


def unload_slash_commands(bot):
    module = inspect.getmodule(inspect.stack()[1][0])
    for name, cls in inspect.getmembers(sys.modules[module.__name__], inspect.isclass):
        if any([issubclass(cls, slashclass) for slashclass in CMDGROUPS]):
            if cls in CMDGROUPS:
                continue
            bot.remove_slash_command(cls.name.lower())
