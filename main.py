from libs.core.conf import settings, buildBash
from libs.core.log import logprint
from libs.core.azura import Azura

import atexit
import os
import pidfile
import sys

if __name__ == "__main__":
    try:
        with pidfile.PIDFile():
            if not os.path.isfile(settings['bot']['bashPath']):
                logprint("Bash file not found.", type="errr")
                logprint("It has been generated. Please start the bot through that.", type="errr")
                buildBash(settings)
                sys.exit(1)
            else:
                azura = Azura()
                atexit.register(azura.deconstruct)
                azura.run()
    except pidfile.AlreadyRunningError:
        logprint("{name} is already running.".format(name=settings['bot']['name']), type="ERRR")
        sys.exit(1)
