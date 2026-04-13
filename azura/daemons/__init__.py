import hikari

from ..core.conf import Config
from ..core.log import logging


conf = Config.load()
logger = logging.getLogger(conf.name).getChild("daemons")


__all__ = [

]


def run_daemons(bot: hikari.GatewayBot) -> None:
    loop = hikari.internal.aio.get_or_make_loop()

    for daemon in __all__:
        daemon = daemon()
        logger.info(f"Starting {daemon.name} daemon")
        daemon.attach_bot(bot)
        loop.create_task(daemon.service())

        