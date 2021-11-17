from core.conf import conf
from core.subordinate import Subordinate

import hikari
import os
from setproctitle import setproctitle
import sys

if os.name != "nt":
    import uvloop

    uvloop.install()

setproctitle("SUB-1")

conf.logger.info("Connecting to API...")
bot = Subordinate("SUB-1", 8086, token=conf.subordinate_tokens[0], prefix=conf.prefix, logs=None, intents=hikari.Intents.ALL)

bot.run(asyncio_debug=False)
