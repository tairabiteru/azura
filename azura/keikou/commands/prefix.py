"""Module subclassing lightbulb's command types"""


from .base import KeikouMixin

import lightbulb


class PrefixCommand(KeikouMixin, lightbulb.PrefixCommand):
    pass


class PrefixSubCommand(KeikouMixin, lightbulb.PrefixSubCommand):
    pass


class PrefixSubGroup(KeikouMixin, lightbulb.PrefixSubGroup):
    pass


class PrefixCommandGroup(KeikouMixin, lightbulb.PrefixCommandGroup):
    pass
