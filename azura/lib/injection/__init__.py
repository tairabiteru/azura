import lightbulb

from .orm import get_user, get_channel, get_guild
from .koe_injection import get_session


__all__ = [
    "get_user",
    "get_channel",
    "get_guild",
    "get_session"
]


def load_injection_for_commands(client: lightbulb.Client):
    for function in __all__:
        function = globals()[function]
        client.di.registry_for(lightbulb.di.Contexts.COMMAND).register_factory(
            function.__annotations__['return'],
            function
        )