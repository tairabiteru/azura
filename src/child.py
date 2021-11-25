from core.conf import conf
from core.child import Child

import hikari
import os
from setproctitle import setproctitle
import sys

if os.name != "nt":
    import uvloop

    uvloop.install()

number = int(sys.argv[1])
name = f"{conf.name}Child-{number}"

setproctitle(name)

conf.logger.info("Connecting to API...")
bot = Child(name, conf.dash.port + number + 1, token=conf.child_tokens[number], prefix=conf.prefix, logs=None, intents=hikari.Intents.ALL)

bot.run(asyncio_debug=False)
