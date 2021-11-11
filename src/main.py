from core.conf import conf
from core.bot import bot

import os
from setproctitle import setproctitle

if os.name != "nt":
    import uvloop

    uvloop.install()

setproctitle(conf.name)

conf.logger.info("Connecting to API...")
bot.run(asyncio_debug=False)
