"""
This module contains all things related to the settings file.

Any defaults or settings are found here, as well as validation for said
settings, and folder creation and validation too.
"""
import os
import sys
import toml
import colorama
from colorama import Fore as color
from colorama import Style
import datetime

colorama.init()

__VERSION__ = "3.0"
__VERSIONTAG__ = "Sapphirine Songstress"

BASE = {
    'name': 'Azura',
    'prefix': '-',
    'description': "An advanced Discord music bot.",
    'timezone': "America/Detroit",
    'activityCycle': ['Use -help'],
    'ownerID': 0,
    'token': "",
    'secret': "",
    'exclusionaryIDs': [],
    'dash': {
        'enabled': False,
        'host': 'localhost',
        'port': 8080,
        'outfacingURL': ''
    },
    'wavelink': {
        'run': True,
        'host': 'localhost',
        'port': 2333,
        'password': "",
        'jvmPath': "java",
        'voiceRegion': 'us_central',
        'verbose': True
    },
    'music': {
        'connectionTimeout': 180,
        'maxHistoryRecords': 1000,
        'enqueueingShotDelay': 0.2,
        'seekBarLength': 40,
    },
    'issues': {
        'validTags': ['open', 'closed', 'critical', 'acknowledged']
    }
}


def recSetAttr(obj, d):
    """
    Set attributes recursively.

    This is an admittedly somewhat dirty method used to get the
    conf.to_have.attributes like that.
    """
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(obj, key, recSetAttr(SubConf(), value))
        else:
            setattr(obj, key, value)
    return obj


def ensure(path):
    """
    Ensure a directory exists during initialization.

    The directory is created if it doesn't exist, unless it can't, in which
    case, the bot crashes.
    """
    try:
        os.makedirs(path)
        Logger().log(f"Directory {path} does not exist. It has been created.", type='warn')
        return path
    except FileExistsError:
        return path
    except PermissionError:
        Logger().log(f"Error creating {path}.", type='crit')
        Logger().log("Fatal, shutting down.", type='crit')
        sys.exit(-1)


class SubConf:
    """Container class to hold subattributes of the config class."""

    def __init__(self):
        """Init nothing lol."""
        pass


class Conf:
    """
    Core configuration container.

    This class both initializes and contains all configuration settings used
    by the bot. It also initializes some internal settings which are not
    exposed in the config file itself. These are used in the code as easy
    shortcuts to particular paths.
    """

    def __init__(self, path="conf.toml"):
        """
        Initialize config.

        We load in conf.toml from the bot's root dir. If it doesn't exist, we
        create a new one from the base settings. Either way, we continue
        on, using the above functions to recursively set attributes to
        values and subdivisions in the toml file.
        The bash file and validation are also performed here prior to
        initialization of the bot itself.
        """
        try:
            self._conf = toml.load(path)
        except FileNotFoundError:
            Logger().log("conf.toml was not found, generating...")
            self._conf = BASE
            with open(path, "w") as confFile:
                toml.dump(self._conf, confFile)

        self._constructPaths()
        self = recSetAttr(self, self._conf)
        self.logger = Logger(logDir=self.logDir, file_prefix=self.name)

        if not self.dash.outfacingURL:
            self.dash.outfacingURL = self.dash.host

        self.buildBash()
        self.validate()

    def _constructPaths(self):
        """
        Initialize internal paths.

        The paths created here are internal, and not exposed in conf.toml.
        They are based on the location of the bot's execution. We also define
        some other internal settings in here too, unrelated to paths.
        """
        self._conf['VERSION'] = __VERSION__
        self._conf['VERSIONTAG'] = __VERSIONTAG__

        root = os.getcwd()
        self._conf['rootDir'] = root
        self._conf['logDir'] = ensure(os.path.join(root, "logs/"))
        self._conf['bashPath'] = os.path.join(root, self._conf['name'].lower() + ".sh")
        self._conf['mainPath'] = os.path.join(root, self._conf['name'].lower() + ".py")
        self._conf['binDir'] = os.path.join(root, "bin/")
        self._conf['storageDir'] = ensure(os.path.join(root, "storage/"))
        self._conf['tempDir'] = ensure(os.path.join(self._conf['storageDir'], "temp/"))
        self._conf['assetDir'] = os.path.join(root, "assets/")

        dashroot = ensure(os.path.join(root, "www/"))
        self._conf['dash']['rootDir'] = dashroot
        self._conf['dash']['templateDir'] = os.path.join(dashroot, "templates/")
        self._conf['dash']['staticDir'] = os.path.join(dashroot, "static/")
        self._conf['dash']['uploadDir'] = ensure(os.path.join(dashroot, "uploads/"))

        self._conf['wavelink']['lavalinkPath'] = os.path.join(self._conf['binDir'], "Lavalink.jar")

        ormroot = ensure(os.path.join(self._conf['storageDir'], "database/"))
        # Define here since there are no configurable ORM options
        self._conf['orm'] = {}
        self._conf['orm']['rootDir'] = ormroot
        self._conf['orm']['memberDir'] = ensure(os.path.join(ormroot, "members/"))
        self._conf['orm']['serverDir'] = ensure(os.path.join(ormroot, "servers/"))
        self._conf['orm']['botDir'] = ensure(os.path.join(ormroot, "bot/"))
        self._conf['orm']['faqDir'] = ensure(os.path.join(self._conf['orm']['botDir'], "faq/"))

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

                bashFile.write(f"LOCKFILE={os.path.join(self.rootDir, f'{self.name}.lock')}\n")
                bashFile.write("if test -f \"$LOCKFILE\"; then\n    rm $LOCKFILE\nfi\n\n")
                bashFile.write(f"while true; do\n    python3 {self.mainPath}\n")
                bashFile.write("    if test -f $LOCKFILE; then\n        break\n    fi\ndone")
            os.system(f"chmod +x {self.bashPath}")

    def validate(self):
        """
        Validate the presence of particular config options.

        In particular, we need to ensure the token, secret, and ownerID are
        all present in the config file, at least. These are the bare minimum
        settings required for the bot to run, and if they're not present on
        initialization, the bot will crash.
        """
        valid = True

        for attr in ['token', 'secret', 'ownerID']:
            if not getattr(self, attr, None):
                self.logger.log(f"{attr} is not set in conf.toml.", type='crit')
                valid = False

        if not valid:
            self.logger.log("Critical settings are missing. Fatal, shutting down.", type='crit')
            sys.exit(-1)


class Logger:
    COLOR_MAP = {
        'INFO': color.WHITE,
        'WARN': color.CYAN,
        'ERRR': color.YELLOW,
        'CRIT': color.RED
    }

    def __init__(self, logDir=None, file_prefix=None):
        self.logDir = logDir
        self.filePrefix = file_prefix

    def banner(self, text):
        """Print the bot's banner."""
        os.system(f"toilet -f mono12 -F gay -F border {text}")

    def version(self, text):
        """Log the bot's version."""
        self.log_to_file(f"\nVersion {text}\n")
        print(color.WHITE + f"\nVersion {text}" + Style.RESET_ALL)

    def latest_log_file(self):
        files = list([file for file in os.listdir(self.logDir) if file.split("_")[0] == self.filePrefix])
        files.sort(key=lambda date: datetime.datetime.strptime(date, f"{self.filePrefix}_%Y-%m-%d.log"))
        return os.path.join(self.logDir, files[-1])

    def log_to_file(self, message):
        """Send logging to file."""
        if self.logDir is not None:
            if self.filePrefix is None:
                fname = datetime.datetime.now().strftime("%Y-%m-%d.log")
            else:
                fname = datetime.datetime.now().strftime(f"{self.filePrefix}_%Y-%m-%d.log")
            with open(os.path.join(self.logDir, fname), 'a') as file:
                file.write(f"{message}\n")

    def log(self, message, type="info"):
        """
        Handle console logging.

        All messages may have a type specified. This changes the color of the
        text which helps certain things stand out in the console.
        """
        type = type.upper()
        timestamp = datetime.datetime.now().strftime('%Y|%m|%d %H:%M:%S')
        color = Logger.COLOR_MAP[type]
        output = f"[{type}][{timestamp}] {message}"
        self.log_to_file(output)
        print(f"{color}{output}{Style.RESET_ALL}")


# Construct config.
conf = Conf()
conf2 = Conf("conf2.toml")

confs = [conf, conf2]
