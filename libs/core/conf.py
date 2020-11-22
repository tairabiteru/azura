"""
This module contains all things related to the settings file.

Any defaults or settings are found here, as well as validation for said
settings, and folder creation and validation too.
"""

from libs.core.log import logprint

import os
import sys
import toml

# Base settings needed by the bot to run.
BASE_SETTINGS = {
    "title": 'Azura Settings',
    "bot": {
        "name": "Azura",
        "majorVersion": "1.0",
        "versionTag": "Dazzling Dancer",
        "commandPrefix": "&",
        "description": "An advanced Discord music bot.",
        "manpageLink": "",
        "timezone": "America/Detroit",
        "ownerID": 0,
        "id": 0,
        "token": "",
        "secret": ""
    }
}


def buildSettings():
    """
    Construct settings file.

    We attempt to load the settings file from botroot/settings.toml,
    but if it's not found, we manually construct a new file.
    """
    try:
        settings = toml.load("settings.toml")
    except FileNotFoundError:
        logprint("settings.toml was not found. Generating...")
        settings = BASE_SETTINGS

        settings['bot']['rootDirectory'] = os.getcwd()
        settings['bot']['bashPath'] = os.path.join(settings['bot']['rootDirectory'], settings['bot']['name'].lower() + ".sh")
        settings['bot']['mainPath'] = os.path.join(settings['bot']['rootDirectory'], "main.py")
        settings['bot']['storageDirectory'] = os.path.join(settings['bot']['rootDirectory'], "storage/")
        settings['bot']['tempDirectory'] = os.path.join(settings['bot']['storageDirectory'], "temp/")
        settings['bot']['assetDirectory'] = os.path.join(settings['bot']['rootDirectory'], "assets/")
        settings['bot']['activityCycle'] = ['Use /help']

        dash = {}
        dash['enabled'] = False
        dash['host'] = "localhost"
        dash['port'] = 8080
        dash['serverInvite'] = ""
        dash['tagsEnabledGuild'] = 0
        dash['rootDirectory'] = os.path.join(settings['bot']['assetDirectory'], "dash")
        dash['templateDirectory'] = os.path.join(dash['rootDirectory'], "templates")
        dash['staticDirectory'] = os.path.join(dash['rootDirectory'], "static")
        dash['fileUploadDirectory'] = os.path.join(dash['rootDirectory'], "file_uploads")
        settings['dash'] = dash

        orm = {}
        orm['databaseDirectory'] = os.path.join(settings['bot']['storageDirectory'], "database/")
        orm['memberDirectory'] = os.path.join(orm['databaseDirectory'], "members/")
        orm['serverDirectory'] = os.path.join(orm['databaseDirectory'], "servers/")
        orm['botDirectory'] = os.path.join(orm['databaseDirectory'], "bot/")
        settings['orm'] = orm

        cogs = {}

        tools = {}
        cogs['tools'] = tools

        issues = {}
        issues['validTags'] = ['open', "closed", 'critical', 'acknowledged']
        cogs['issues'] = issues

        settings['cogs'] = cogs

        with open("settings.toml", "w") as settingsfile:
            toml.dump(settings, settingsfile)

    return settings


def buildBash(settings):
    """
    Build the bash file the bot is executed with.

    We check for the presence of the file first, and if it's not present,
    we construct it manually.
    """
    if not os.path.isfile(settings['bot']['bashPath']):
        with open(settings['bot']['bashPath'], "w") as bashFile:
            bashFile.write("#!/bin/bash\n")
            bashFile.write("cd {root}\n".format(root=settings['bot']['rootDirectory']))

            bashFile.write("LOCKFILE={lf}\n".format(lf=os.path.join(settings['bot']['rootDirectory'], "lock")))
            bashFile.write("if test -f \"$LOCKFILE\"; then\n    rm $LOCKFILE\nfi\n\n")
            bashFile.write("while true; do\n    python3 {main}\n".format(main=settings['bot']['mainPath']))
            bashFile.write("    if test -f $LOCKFILE; then\n        break\n    fi\ndone")
        os.system("chmod +x {bash}".format(bash=settings['bot']['bashPath']))


def validateDirectories(settings, root):
    """Check to make sure all key directories exist."""
    for key, value in settings.items():
        if isinstance(value, dict):
            validateDirectories(value, root)
        else:
            if "Directory" in key:
                if not os.path.isdir(value):
                    if value.startswith(root):
                        logprint("Directory '" + value + "' does not exist. Creating...")
                        os.makedirs(value)
                    else:
                        logprint("The settings file path " + value + " does not exist", type="warn")


def validateSettings(settings):
    """Validate settings. Called during startup."""
    validateDirectories(settings, settings['bot']['rootDirectory'])

    if not settings['bot']['token']:
        logprint("Token has not been defined in settings.toml.", type='crit')
        logprint("Fatal, shutting down.", type='crit')
        sys.exit(-1)


# Construct settings variable so it can be imported, and validate.
settings = buildSettings()
validateSettings(settings)
