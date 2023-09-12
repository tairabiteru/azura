"""Module overriding the default uvicorn server

The reason we do this is primarily because uvicorn messes with
signal handlers, which is not desirable because we're going to handle
those ourselves. Unless overriden, the default uvicorn server will fail
to shut down when the bot does, causing the server to fail to initialize
upon reboot because the port is occupied by the old server. We also override
the shutdown here to print a confirmation message because it's nice.

    * UvicornServer - An overriden class doing the above
"""
from ...core.conf import Config

conf = Config.load()


import os
import sass
import uvicorn


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass
    
    def compile_sass(self):
        sass_root = os.path.join(conf.mvc.static_root, "sass")
        css_root = os.path.join(conf.mvc.static_root, "css")

        sass.compile(dirname=(sass_root, css_root))
    
    async def shutdown(self, bot, *args, **kwargs):
        bot.logger.warning("Internal webserver shutting down.")
        return await super().shutdown(*args, **kwargs)

    async def serve(self, *args, **kwargs):
        self.compile_sass()
        return await super().serve(*args, **kwargs)