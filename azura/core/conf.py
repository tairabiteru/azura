import colorlog
import fernet
import logging
import os
import toml
import types
from logging.handlers import TimedRotatingFileHandler
import pathlib


COLORS = {
    "DEBUG": "light_blue",
    "INFO": "light_green",
    "WARNING": "light_yellow",
    "ERROR": "light_red",
    "CRITICAL": "light_purple",
}


stdhandler = colorlog.StreamHandler()
stdhandler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s][HIKARI][%(levelname)s] %(message)s",
        datefmt="%x %X",
        reset=True,
        log_colors=COLORS,
    )
)

if not os.path.exists("logs/"):
    os.mkdir("logs/")

filehandler = TimedRotatingFileHandler("logs/bot.log", when="midnight")
filehandler.setFormatter(logging.Formatter("[%(asctime)s][HIKARI][%(levelname)s] %(message)s"))

logger = colorlog.getLogger("bot")
logger.addHandler(stdhandler)
logger.addHandler(filehandler)


__VERSION__ = "4.2 β"
__VERSION_TAG__ = "Indigo Idol"


BASE = {
    'owner_id': 0,
    'timezone': 'UTC',
    'temp_dir': "/dev/shm",
    'postgres_uri': 'postgres://postgres:password@localhost:5432/database',
    'hikari_loglevel': "",
    'message_resend_interval': 3300,
    'lavalink': {
        'host': 'localhost',
        'port': 2333,
        'password': ""
    },
    'dash': {
        'enabled': False,
        'key': str(fernet.Fernet.generate_key()),
        'outfacing_url': 'http://localhost'
    },
    'bots': [
        {
            'name': "azura",
            'token': "",
            'host': 'localhost',
            'port': 8080,
            'is_parent': True
        },
        {
            'name': "olivia",
            'token': "",
            'host': 'localhost',
            'port': 8081,
            'is_parent': False
        }
    ]
}


class ConfigurationError(Exception):
    pass


class ConfigNamespace(types.SimpleNamespace):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, dict):
                kwargs[key] = ConfigNamespace(**value)
            elif isinstance(value, list):
                new_value = []
                for item in value:
                    if isinstance(item, dict):
                        item = ConfigNamespace(**item)
                    new_value.append(item)
                kwargs[key] = new_value
        super().__init__(**kwargs)


class Configuration(ConfigNamespace):
    def __init__(self):
        try:
            self._conf = toml.load("conf.toml")
            self.logger = logger
        except FileNotFoundError:
            self._conf = BASE
            with open("conf.toml", "w") as conf_file:
                toml.dump(self._conf, conf_file)

        self._conf['VERSION'] = __VERSION__
        self._conf['VERSION_TAG'] = __VERSION_TAG__
        self._conf['root_dir'] = pathlib.Path(__file__).parent.parent.parent.resolve()

        self._conf['dash']['root_dir'] = "www/"
        self._conf['dash']['static_dir'] = os.path.join(self._conf['dash']['root_dir'], "static/")
        self._conf['dash']['template_dir'] = os.path.join(self._conf['dash']['root_dir'], "templates/")
        super().__init__(**self._conf)

        self.orm_config = {
            'connections': {
                'default': self._conf['postgres_uri'],
            },
            'apps': {
                'models': {
                    'models': ['orm.models', 'aerich.models'],
                    'default_connection': 'default'
                }
            }
        }

    def get_bot(self, name):
        for bot in self.bots:
            if bot.name == name:
                return bot
        else:
            raise ConfigurationError(f"No bot with the name `{name}` exists.")

    def get_parent(self):
        for bot in self.bots:
            if bot.is_parent is True:
                return bot

    def get_children(self):
        bots = []
        for bot in self.bots:
            if bot.is_parent is False:
                bots.append(bot)
        return bots

    @property
    def children(self):
        return self.get_children()

    @property
    def parent(self):
        return self.get_parent()

    def validate(self):
        all_bots = []
        parent = None
        for bot in self.bots:
            if bot.is_parent is True:
                if parent is not None:
                    raise ConfigurationError(f"{bot.name} is defined as a parent, but so is {parent.name}. There may only be one parent.")
                parent = bot

            if bot.name in all_bots:
                raise ConfigurationError(f"More than one bot has the name {bot.name}. Bot names must be unique.")
            all_bots.append(bot.name)

        if parent is None:
            raise ConfigurationError("No bots are defined as the parent. At least one must be defined so.")


conf = Configuration()
