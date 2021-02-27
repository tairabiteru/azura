"""Contains all global subroutines."""

from libs.core.conf import conf
from libs.orm.uptime import UptimeRecords

import concurrent.futures
import discord
from discord.ext import tasks
import itertools
import traceback


hearts = itertools.cycle(conf.activityCycle)


@tasks.loop(seconds=5.0)
async def heartbeat(bot):
    """Activity loop, basically."""
    await bot.wait_until_ready()
    act = discord.Game(name=next(hearts))
    await bot.change_presence(activity=act)


@tasks.loop(seconds=5)
async def uptime_tracker():
    """Track uptime."""
    try:
        master_record = UptimeRecords.obtain()
        master_record.current_uptime.update()
    except Exception as e:
        print(e)
        if isinstance(e, concurrent.futures.CancelledError):
            pass
        else:
            traceback.print_exc()


@uptime_tracker.before_loop
async def before_uptime_tracker(bot):
    """Prepare new uptime record."""
    await bot.wait_until_ready()
    master_record = UptimeRecords.obtain()
    master_record.new_uptime_record()


def setup(bot):
    """Set up and run subroutines."""
    subroutines = []
    subroutines.append(heartbeat.start(bot))
    subroutines.append(uptime_tracker.start(bot))
    bot.subroutines = subroutines
