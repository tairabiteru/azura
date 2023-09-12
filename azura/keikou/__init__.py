"""Module defining keikou

Keikou is Farore's custom command management system. Keikou is responsible
for the automatic implementation of the /help command, as well as the
automatic permissions definition system which underlies all command execution
Farore performs. At its core, Keikou is a heavily modified version of Hikari Lightbulb.
"""

__all__ = [
    "EXPLICIT",
    "IMPLICIT",
    "CheckFailure",
    "CommandErrorEvent",
    "CommandInvocationError",
    "HelpTopic",
    "PermissionsManager",
    "Plugin",
    "PluginTopic",
    "PrefixCommand",
    "PrefixCommandGroup",
    "PrefixSubCommand",
    "PrefixSubGroup"
    "SlashCommand",
    "SlashCommandGroup",
    "SlashSubCommand",
    "SlashSubGroup",
    "Topic",
    "command",
    "evaluate_permissions"
    "implements",
    "option"
]

from lightbulb import *

from .commands import *
from .decorators import *
from .help import *
from .permissions import *
from .plugins import *
