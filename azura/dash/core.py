from core.conf import conf
from dash.filters import filters

import importlib
import jinja2
import sanic
import sanic_session
import sanic_jinja2


LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'colored': {
            '()': 'colorlog.ColoredFormatter',
            'format': "%(log_color)s[%(asctime)s][SANIC][%(levelname)s] %(message)s",
            'datefmt': '%x %X',
            'reset': True,
            'log_colors': {
                "DEBUG": "light_blue",
                "INFO": "light_green",
                "WARNING": "light_yellow",
                "ERROR": "light_red",
                "CRITICAL": "light_purple",
            }
        },
        'standard': {
            'format': "[%(asctime)s][SANIC][%(levelname)s] %(message)s"
        }
    },
    'handlers': {
        'default': {
            'formatter': 'colored',
            'class': 'colorlog.StreamHandler'
        },
        'file': {
            'formatter': 'standard',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': "logs/bot.log",
            'when': "midnight"
        }
    },
    'loggers': {
        'sanic.root': {
            'handlers': ['default', 'file'],
            'level': 'ERROR'
        },
        'sanic.error': {
            'handlers': ['default', 'file'],
            'level': 'ERROR'
        },
        'sanic.access': {
            'level': 'CRITICAL',
            'handlers': []
        }
    }
}


class Dash:
    def __init__(self, bot):
        self.bot = bot

        self.app = sanic.Sanic(
            name=self.bot.conf.name,
            log_config=LOG_CONFIG
        )

        self.app.static("/static", conf.dash.static_dir)

        loader = jinja2.FileSystemLoader(conf.dash.template_dir)
        session = sanic_session.Session(self.app, interface=sanic_session.InMemorySessionInterface())
        self.app.ctx.session = session
        self.app.ctx.jinja = sanic_jinja2.SanicJinja2(self.app, loader=loader)
        for filter in filters:
            self.app.ctx.jinja.add_env(filter.__name__, filter, scope="filters")
        self.app.ctx.bot = self.bot

        if self.bot.type.value == "PARENT":
            self.loadRoutes("dash.routes.index")
            self.loadRoutes("dash.routes.playlists")
        self.loadRoutes("dash.routes.api")

    def loadRoutes(self, routeFile):
        module = importlib.import_module(routeFile)
        if not hasattr(module, "routes"):
            raise ValueError(f"Route file {routeFile} is missing the global 'routes' definition.")
        self.app.blueprint(module.routes)

    async def run(self):
        server = await self.app.create_server(
            host=self.bot.conf.host,
            port=self.bot.conf.port,
            access_log=False,
            debug=False,
            return_asyncio_server=True
        )
        await server.startup()
        return server
