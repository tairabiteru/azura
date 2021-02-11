from libs.core.conf import conf
from libs.core.log import logprint
from libs.core.azura import Azura

import atexit
import os
import pidfile
import sys

if __name__ == "__main__":
    try:
        with pidfile.PIDFile():
            azura = Azura()
            atexit.register(azura.deconstruct)
            azura.run()
    except pidfile.AlreadyRunningError:
        logprint(f"{bot.name} is already running.", type="ERRR")
        sys.exit(1)
