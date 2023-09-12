"""Module subclassing Lightbulb's slash command types"""


from .base import KeikouMixin

import lightbulb


class SlashCommand(KeikouMixin, lightbulb.SlashCommand):
    pass


class SlashSubCommand(KeikouMixin, lightbulb.SlashSubCommand):
    pass


class SlashSubGroup(KeikouMixin, lightbulb.SlashSubGroup):
    pass


class SlashCommandGroup(KeikouMixin, lightbulb.SlashCommandGroup):
    pass
