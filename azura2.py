from libs.core.conf import conf2 as conf
from libs.core.azura2 import Azura

import atexit
import pidfile
import sys

if __name__ == "__main__":
    try:
        with pidfile.PIDFile(filename="azura2.pid"):
            azura = Azura()
            atexit.register(azura.deconstruct)
            azura.run()
    except pidfile.AlreadyRunningError:
        conf.logger.log("Bot is already running.", type="ERRR")
        sys.exit(1)
