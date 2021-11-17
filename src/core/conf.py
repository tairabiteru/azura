"""
This module contains all things related to the settings file.

Any defaults or settings are found here, as well as validation for said
settings, and folder creation and validation too.
"""
import colorlog
import fernet
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import quantumrandom
import sys
import time
import toml


def initLogger(name):
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
            "%(log_color)s[%(asctime)s][%(name)s][%(levelname)s] %(message)s",
            datefmt="%x %X",
            reset=True,
            log_colors=COLORS,
        )
    )

    if not os.path.exists("logs/"):
        os.mkdir("logs/")

    filehandler = TimedRotatingFileHandler("logs/bot.log", when="midnight")
    filehandler.setFormatter(logging.Formatter("[%(asctime)s][%(name)s][%(levelname)s] %(message)s"))

    logger = colorlog.getLogger(name)
    logger.addHandler(stdhandler)
    logger.addHandler(filehandler)
    return logger


logger = initLogger("MASTER")


__VERSION__ = "4.0 α"
# 4 will be Ultramarine Umbra
__VERSIONTAG__ = "Ultramarine Umbra"

BASE = {
    "name": "Azura",
    "prefix": "#!",
    "description": "An advanced music bot.",
    "timezone": "America/Detroit",
    "loglevel": "INFO",
    "hikari_loglevel": "",
    "activityCycle": ["Use .help"],
    "terminalPath": "/path/to/terminal/binary",
    "tempDir": "",
    "ownerID": 0,
    "token": "",
    "secret": "",
    "subordinate_tokens": [],
    "dash": {
        "enabled": False,
        "key": str(fernet.Fernet.generate_key()),
        "host": "http://localhost",
        "port": 8080,
        "outfacingURL": "",
        "serverInvite": ""
    },
    "audio": {
        "lavalink_enabled": True,
        "lavalink_addr": "localhost",
        "lavalink_port": 2333,
        "lavalink_pass": ""
    }
}


def recSetAttr(obj, d):
    """Set attributes recursively."""
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(obj, key, recSetAttr(SubConf(), value))
        else:
            setattr(obj, key, value)
    return obj


def ensure(path):
    """Ensure the existence of a path."""
    try:
        os.makedirs(path)
        logger.warning(f"Directory {path} does not exist. It has been created.")
        return path
    except FileExistsError:
        return path
    except PermissionError:
        logger.critical(f"Error creating {path}.")
        logger.critical("Fatal, shutting down.")
        sys.exit(-1)


class SubConf:
    """Blank class to serve as attribute for Conf."""

    def __init__(self):
        """Do nothing."""
        pass


class Conf:
    """Contain and build configuration from file."""

    def __init__(self):
        """Initialize configuration from TOML file, building one if not found."""
        try:
            self._conf = toml.load("conf.toml")
        except FileNotFoundError:
            logger.info("conf.toml was not found, generating...")
            self._conf = BASE
            with open("conf.toml", "w") as confFile:
                toml.dump(self._conf, confFile)

        self._constructPaths()
        self = recSetAttr(self, self._conf)
        self.logger = logger
        self.logger.setLevel(self._conf["loglevel"])

        if not self.dash.outfacingURL:
            self.dash.outfacingURL = self.dash.host

        self.buildBash()
        self.validate()

    @property
    def trngSeed(self):
        """Generate TRNG seed."""
        t = map(int, str(time.time()).split("."))
        return self.qrngSeed * sum(t)

    def _constructPaths(self):
        self._conf["VERSION"] = __VERSION__
        self._conf["VERSIONTAG"] = __VERSIONTAG__

        self._conf["qrngSeed"] = quantumrandom.randint(0, 1000000000000000000)

        root = os.getcwd()
        self._conf["rootDir"] = root
        self._conf["logDir"] = ensure(os.path.join(root, "logs/"))
        self._conf["bashPath"] = os.path.join(root, self._conf["name"].lower() + ".sh")
        self._conf["mainPath"] = os.path.join(root, "main.py")
        self._conf["binDir"] = os.path.join(root, "bin/")
        self._conf["storageDir"] = ensure(os.path.join(root, "storage/"))

        if self._conf["tempDir"] == "":
            self._conf["tempDir"] = ensure(os.path.join(self._conf["storageDir"], "temp/"))

        self._conf["assetDir"] = os.path.join(root, "assets/")

        dashroot = ensure(os.path.join(root, "www/"))
        self._conf["dash"]["rootDir"] = dashroot
        self._conf["dash"]["templateDir"] = os.path.join(dashroot, "templates/")
        self._conf["dash"]["staticDir"] = os.path.join(dashroot, "static/")

        ormroot = ensure(os.path.join(self._conf["storageDir"], "database/"))
        # Define here since there are no configurable ORM options
        self._conf["orm"] = {}
        self._conf["orm"]["rootDir"] = ormroot
        self._conf["orm"]["memberDir"] = ensure(os.path.join(ormroot, "members/"))
        self._conf["orm"]["serverDir"] = ensure(os.path.join(ormroot, "servers/"))
        self._conf["orm"]["botDir"] = ensure(os.path.join(ormroot, "bot/"))

    def buildBash(self):
        """
        Build the bash file the bot is executed with.

        We check for the presence of the file first, and if it's not present,
        we construct it manually.
        """
        if not os.path.isfile(self.bashPath):
            with open(self.bashPath, "w") as bashFile:
                bashFile.write("#!/bin/bash\n")
                bashFile.write(f"cd {self.rootDir}\n")

                bashFile.write(f"LOCKFILE={os.path.join(self.rootDir, 'lock')}\n")
                bashFile.write('if test -f "$LOCKFILE"; then\n    rm $LOCKFILE\nfi\n\n')
                bashFile.write(f"while true; do\n    python3 {self.mainPath}\n")
                bashFile.write(
                    "    if test -f $LOCKFILE; then\n        break\n    fi\ndone"
                )
            os.system(f"chmod +x {self.bashPath}")

    def validate(self):
        """Validate key settings prior to initialization."""
        valid = True
        for attr in ["token", "secret", "ownerID"]:
            if not getattr(self, attr, None):
                self.logger.critical(f"{attr} is not set in conf.toml.")
                valid = False
        if not valid:
            self.logger.critical("Critical settings are missing. Fatal, shutting down.")
            sys.exit(-1)

        if not os.path.exists(self.tempDir):
            self.logger.critical(f"Temporary directory path {self.tempDir} does not exist.")
            self.logger.critical("Temporary directory is required for operation. Fatal, shutting down.")
            sys.exit(-1)


conf = Conf()
