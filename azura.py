from libs.core.conf import conf
from libs.core.azura import Azura

import atexit
import pidfile
import sys

if __name__ == "__main__":
    try:
        with pidfile.PIDFile(filename="azura.pid"):
            azura = Azura()
            atexit.register(azura.deconstruct)
            azura.run()
    except pidfile.AlreadyRunningError:
        conf.logger.log("Bot is already running.", type="ERRR")
        sys.exit(1)
