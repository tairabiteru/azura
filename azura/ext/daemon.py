"""Module defining daemons

Daemons, with regard to Farore, are background tasks. The module
that follows defines the behavior of them, as well as interfaces
for Farore to interact with them, and shut them down when need be.
Most daemons are defined within core.bot.

    * Daemon - Class abstracting a daemon
    * daemon - Decorator which turns a function into a daemon with the specific execution period
"""

import asyncio


class Daemon:
    ALL = []

    def __init__(self, callback, seconds, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.seconds = seconds
        self._bot = None
    
    def attach_bot(self, bot):
        self._bot = bot
    
    @property
    def bot(self):
        if not self._bot:
            raise ValueError("Bot not attached.")
        return self._bot
    
    async def service(self):
        while True:
            await self.callback(self.bot, *self.args, **self.kwargs)
            await asyncio.sleep(self.seconds)


def daemon(seconds=0, minutes=0, hours=0, days=0):
    seconds = seconds + (minutes * 60) + (hours * 3600) + (days * 86400)
    if seconds <= 0:
        raise ValueError("The total time for a daemon's execution cannot be 0.")
    
    def inner(func):
        def inner_inner(*args, **kwargs):
            return Daemon(func, seconds, *args, **kwargs)
        Daemon.ALL.append(inner_inner)
        return inner_inner
    return inner