import argparse
import logging
import os
import pidfile
import setproctitle
import uvloop

from core.bot import Bot
from core.conf import conf, ConfigurationError


parser = argparse.ArgumentParser()
parser.add_argument("--name", help="The name of the bot to start, as defined in conf.toml. If not specified, the parent will be started.")
parser.add_argument("--asyncio-debug", action="store_true", help="Enable asyncio debug.")
parser.add_argument("--force-reinit", action="store_true", help="Force the reinitialization of the specified bot.")
parser.add_argument("--init-children", action="store_true", help="When used with the parent, the child bots will also be started.")
parser.add_argument("--multiplex", action="store_true", help="Begin the process in a GNU Screen multiplexed session.")


logger = logging.getLogger("root")


def main():
    if os.name == "nt":
        logger.critical("Azura is not supported on NT based (Windows) systems.")
        return -1

    uvloop.install()
    args = parser.parse_args()

    if args.asyncio_debug is True:
        logger.warning("Asyncio debug is active.")

    try:
        conf.validate()
    except ConfigurationError as e:
        logger.critical(str(e))
        return -2

    bot = Bot(args.name)

    if args.init_children is True:
        try:
            bot.initialize_children()
        except ValueError:
            bot.logger.critical(f"{bot.name} is not a parent bot, so the --init_children argument cannot be used.")
            return -3
    try:
        with pidfile.PIDFile(filename=f"{bot.conf.name}.pid"):
            setproctitle.setproctitle(bot.conf.name)
            bot.logger.info("Connecting to API...")
            bot.run(asyncio_debug=args.asyncio_debug)
    except pidfile.AlreadyRunningError:
        logger.critical(f"{bot.name} is already running.")
        return -4


if __name__ == '__main__':
    main()
