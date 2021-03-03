"""
This module contains all things related to the settings file.

Any defaults or settings are found here, as well as validation for said
settings, and folder creation and validation too.
"""

from libs.core.log import logprint

import os
import sys
import toml

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
    'dash': {
        'enabled': False,
        'host': 'localhost',
        'port': 8080,
        'outfacingURL': ''
    },
    'wavelink': {
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
        logprint(f"Directory {path} does not exist. It has been created.", type='warn')
        return path
    except FileExistsError:
        return path
    except PermissionError:
        logprint(f"Error creating {path}.", type='crit')
        logprint("Fatal, shutting down.", type='crit')
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

    def __init__(self):
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
            self._conf = toml.load("conf.toml")
        except FileNotFoundError:
            logprint("conf.toml was not found, generating...")
            self._conf = BASE
            with open("conf.toml", "w") as confFile:
                toml.dump(self._conf, confFile)

        self._constructPaths()

        self = recSetAttr(self, self._conf)

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
        self._conf['bashPath'] = os.path.join(root, self._conf['name'].lower() + ".sh")
        self._conf['mainPath'] = os.path.join(root, "main.py")
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

                bashFile.write(f"LOCKFILE={os.path.join(self.rootDir, 'lock')}\n")
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
                logprint(f"{attr} is not set in conf.toml.", type='crit')
                valid = False

        if not valid:
            logprint("Critical settings are missing. Fatal, shutting down.", type='crit')
            sys.exit(-1)


# Construct config.
conf = Conf()
