import logging

from .conf import Config
from .log_base import get_handlers


conf: Config = Config.load()


for logger, level in conf.logging.levels.items():
    if logger == "bot":
        logger = logging.getLogger(conf.name)
        logger.handlers.clear()
    else:
        logger = logging.getLogger(logger)
    
    logger.setLevel(level)

    for handler in get_handlers(fmt=conf.logging.format, date_fmt=conf.logging.date_format):
        logger.addHandler(handler)
