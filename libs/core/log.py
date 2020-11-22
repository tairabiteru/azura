"""
This module defines the simple logging system.

All console messages are piped through `logprint`.
"""

import colorama
from colorama import Fore as color
from colorama import Style
import datetime
import os

colorama.init()


def toilet_banner(text):
    """Print the bot's banner."""
    os.system("toilet -f mono12 -F gay -F border {text}".format(text=text))


def toilet_version(text):
    """Print the bot's version text."""
    print(color.WHITE + "Version {text}".format(text=text) + Style.RESET_ALL)


def logprint(message, type="mesg"):
    """
    Handle console logging.

    All messages may have a type specified. This changes the color of the text
    which helps certain things stand out in the console.
    """
    type = type.upper()
    if type not in ['MESG', 'WARN', 'ERRR', 'CRIT']:
        raise ValueError("type must be one of 'mesg', 'warn', 'errr', 'crit'")

    now = datetime.datetime.now()
    timestamp = now.strftime('%Y|%m|%d %H:%M:%S')
    if type == "MESG":
        print(color.WHITE + "[{type}][{timestamp}] ".format(type=type.upper(), timestamp=timestamp) + message + Style.RESET_ALL)
    if type == "WARN":
        print(color.CYAN + "[{type}][{timestamp}] ".format(type=type.upper(), timestamp=timestamp) + message + Style.RESET_ALL)
    if type == "ERRR":
        print(color.YELLOW + "[{type}][{timestamp}] ".format(type=type.upper(), timestamp=timestamp) + message + Style.RESET_ALL)
    if type == "CRIT":
        print(color.RED + "[{type}][{timestamp}] ".format(type=type.upper(), timestamp=timestamp) + message + Style.RESET_ALL)
