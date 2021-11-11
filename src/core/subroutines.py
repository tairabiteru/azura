import asyncio
import hikari
import inspect
import sys


class Subroutine:
    def __init__(self, function, seconds, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.seconds = seconds

    async def task(self):
        while True:
            await self.function(*self.args, **self.kwargs)
            await asyncio.sleep(self.seconds)


def subroutine(seconds=0, minutes=0, hours=0, days=0):
    seconds = seconds + (minutes * 60) + (hours * 3600) + (days * 86400)
    if seconds <= 0:
        raise ValueError("The total time of a subroutine cannot be 0.")

    def decorator(function):
        def wrapper(*args, **kwargs):
            return Subroutine(function, seconds, *args, **kwargs)

        return wrapper

    return decorator


def execute_in_background(func):
    loop = hikari.internal.aio.get_or_make_loop()
    return loop.create_task(func)


def load_subroutines(bot):
    module = inspect.getmodule(inspect.stack()[1][0])
    for name, member in inspect.getmembers(sys.modules[module.__name__]):
        if isinstance(member, Subroutine) and member != Subroutine:
            print(member)
            bot.add_subroutine(member)


def unload_subroutines(bot):
    module = inspect.getmodule(inspect.stack()[1][0])
    for name, member in inspect.getmembers(sys.modules[module.__name__]):
        if isinstance(member, Subroutine) and member != Subroutine:
            bot.halt_subroutine(member)
