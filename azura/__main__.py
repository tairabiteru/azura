import logging
import os
import screenutils
import sys

from core.conf import conf, ConfigurationError
from main import parser


logger = logging.getLogger('root')


def get_or_create_screen(name):
    for screen in screenutils.list_screens():
        if screen.name.lower() == name.lower():
            return (screen, True)
    else:
        screen = screenutils.Screen(name.lower())
        return (screen, False)


def generate_bash(bot, argv=[]):
    bash = "if [ -f \"{bot.name}.lock\" ]; then "
    bash += f"rm {bot.name}.lock; fi; "
    bash += "while true; "
    bash += "do python3.11 -O azura/main.py "
    bash += " ".join(argv[1:]) + "; "
    bash += f"if [ -f \"{bot.name}.lock\" ]; then "
    bash += "break; fi; done;"
    return bash


def main():
    args = parser.parse_args()
    conf.validate()

    if args.name is not None:
        try:
            bot = conf.get_bot(args.name)
        except ConfigurationError:
            logger.critical(f"A bot with the name {args.name} does not exist.")
            return -1
    else:
        bot = conf.get_parent()

    if args.multiplex is True:
        logger.info("Multiplexer active.")
        screen, exists = get_or_create_screen(bot.name.lower())
        if exists is True:
            logger.critical(f"{bot.name} already has an open screen session.")
            return 0

        logger.info("Beginning multiplexed session...")
        bash_cmd = generate_bash(bot, sys.argv)
        os.system(f"screen -S {bot.name.lower()} -dm bash -c '{bash_cmd}'")
        logger.info(f"Session created on screen '{bot.name.lower()}'")
        return 0
    else:
        screen, exists = get_or_create_screen(bot.name.lower())
        if exists is True:
            logger.info("Multiplexed session detected, reconnecting.")
            os.system(f"screen -r {screen.name.lower()}")
            return 0
        bash_cmd = generate_bash(bot, sys.argv)
        os.system(f"bash -c '{bash_cmd}'")


if __name__ == '__main__':
    main()
