import io

import hikari
import hikari.internal
import uvicorn
from django.core.management import call_command

from ..lib.utils import port_in_use
from .conf import Config
from .log import logging

conf: Config = Config.load()
logger = logging.getLogger(conf.name).getChild("http")


class HTTPDaemon(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        """Overload this because they mess with azura's signal handlers."""
        pass

    async def shutdown(self, *args, **kwargs) -> None:
        """Shutdown webserver."""
        return await super().shutdown(*args, **kwargs)

    async def serve(self, *args, **kwargs) -> None:
        """Serve the webserver."""
        return await super().serve(*args, **kwargs)

    @classmethod
    async def run(cls, bot: hikari.GatewayBot):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Run the webserver."""
        if port_in_use(conf.mvc.port):
            logger.error(
                f"Failed to bind to {conf.mvc.host}:{conf.mvc.port}. It is already in use."
            )
            return

        output = io.StringIO()
        call_command("collectstatic", interactive=False, stdout=output)
        output.seek(0)
        output = output.read().strip()
        logger.info(output)

        loop = hikari.internal.aio.get_or_make_loop()  # pyright: ignore[reportAttributeAccessIssue]
        loop.bot = bot

        config: uvicorn.Config = uvicorn.Config(
            f"{conf.name.lower()}.mvc.core.asgi:application",
            host=conf.mvc.host,
            port=conf.mvc.port,
            log_config=None,  # set by core/log.py
            log_level=None,  # set by core/log.py
            lifespan="off",
            loop=loop,
        )

        http_daemon = cls(config)
        loop.create_task(http_daemon.serve())

        logger.info(
            f"Starting internal ASGI webserver on {conf.mvc.host}:{conf.mvc.port}."
        )
        return http_daemon
