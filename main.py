from libs.core.log import logprint
from libs.core.azura import Azura

import atexit
import pidfile
import sys

if __name__ == "__main__":
    try:
        with pidfile.PIDFile():
            azura = Azura()
            atexit.register(azura.deconstruct)
            azura.run()
    except pidfile.AlreadyRunningError:
        logprint("Bot is already running.", type="ERRR")
        sys.exit(1)
