from .conf import Config

conf = Config.load()

import sys
import functools
import asyncio
import os
import code

from ..ext.utils import lint


class Prompt:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.q = asyncio.Queue()
        self.loop.add_reader(sys.stdin, self.got_input)
    
    def got_input(self):
        asyncio.ensure_future(self.q.put(sys.stdin.readline()), loop=self.loop)
    
    async def __call__(self, msg, end='\n', flush=False):
        print(msg, end=end, flush=flush)
        return (await self.q.get()).rstrip("\n")


def clear_last(lines=1):
    for i in range(0, lines):
        print ("\033[A                                                                                                                                                   \033[A")


async def console(bot, loop):
    prompt = Prompt(loop=loop)
    ainput = functools.partial(prompt, end='', flush=True)
    line_count = 0
    default_locals = {'bot': bot}
    interpreter = code.InteractiveConsole(locals=default_locals)

    while bot.is_alive:
        stdin = await ainput(f"\x1b[36;1m{conf.name}>>> ")
        line_count += 1
        
        if not stdin:
            continue

        if stdin in ["reinit", "restart"]:
                await bot.reinit()
                return
        if stdin in ["lint"]:
            lint(os.path.join(conf.root, "azura/"))
            continue
        if stdin in ['exit()', 'exit', 'quit()', 'quit']:
            await bot.kill()
            return

        try:
            interpreter.runsource(stdin)
        except SystemExit:
            interpreter = code.InteractiveConsole(locals=default_locals)