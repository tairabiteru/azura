import colorlog
from cysystemd import journal
import logging
import typing as t


APPLICATION_NAME = "azura"
DEFAULT_FACTORY = logging.getLogRecordFactory()
DEFAULT_FORMAT = "%(log_color)s[%(levelletter)s][%(asctime)s][%(name)s] %(message)s"
DEFAULT_DATE = "%x %X"


def record_factory(*args, **kwargs):
    record = DEFAULT_FACTORY(*args, **kwargs)
    record.levelletter = record.levelname[0]
    return record


def get_handlers(
        record_factory=record_factory,
        fmt=DEFAULT_FORMAT, 
        date_fmt=DEFAULT_DATE
    ) -> t.List[logging.Handler]:
    logging.setLogRecordFactory(record_factory)
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            f"%(log_color)s{DEFAULT_FORMAT}",
            datefmt=DEFAULT_DATE,
            reset=True,
            log_colors={
                'DEBUG': 'blue',
                'INFO': 'cyan',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white'
            }
        )
    )
    return [handler, journal.JournaldLogHandler()]


def get_base_logger(name=APPLICATION_NAME, level="INFO") -> logging.Logger:
    logger = logging.getLogger(name) 
    logger.setLevel(level)
    for handler in get_handlers():
        logger.addHandler(handler)
    return logger