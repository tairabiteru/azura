"""Module which subclasses the Lightbulb commands to work with Keikou"""

__all__ = [
    "CommandLike",
    "PrefixCommand",
    "PrefixSubCommand",
    "PrefixCommandGroup",
    "PrefixSubGroup",
    "SlashCommand",
    "SlashSubCommand",
    "SlashCommandGroup",
    "SlashSubGroup"
]

from .base import *
from .prefix import *
from .slash import *
