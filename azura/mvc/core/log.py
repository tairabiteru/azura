from ...core.log import logging
from ...core.conf import Config


conf = Config.load()
logger = logging.getLogger(conf.name)
logger = logger.getChild("mvc")