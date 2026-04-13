"""Module defining background timer

One of Elysia's functions is the ability to set timers and notify users
when the timer has lapsed.

    * BackgroundTimerError - Generic error thrown when something goes wrong with the timer
    * BackgroundTimer - Implementation of the timer itself
"""
from .utils import utcnow, strfdelta

import asyncio
import datetime
import hikari
import lightbulb
import typing as t
import zoneinfo


class BackgroundTimerError(Exception):
    pass


class BackgroundTimer:
    ALLOWED_FORMATS: t.List[str] = [
        "%I:%M:%S %p",
        "%I:%M:%S%p",
        "%I:%M %p",
        "%I:%M%p",
        "%I %p",
        "%I%p",
    ]

    def __init__(
            self,
            ctx: lightbulb.Context,
            seconds: t.Optional[int]=None, 
            time: t.Optional[str]=None, 
            timezone: zoneinfo.ZoneInfo=zoneinfo.ZoneInfo("UTC")
        ) -> None:
        self.ctx: lightbulb.Context = ctx
        self.channel_id: hikari.Snowflakeish = ctx.channel_id
        self.seconds: t.Optional[int] = seconds
        self.time: t.Optional[str] = time
        self.timezone: zoneinfo.ZoneInfo = timezone

        if seconds is None and time is None:
            raise ValueError("`seconds` and `time` kwargs cannot both be None.")
        if seconds is not None and time is not None:
            raise ValueError("`seconds` and `time` kwargs cannot both be set.")

        if time is not None:
            for format in BackgroundTimer.ALLOWED_FORMATS:
                try:
                    self.time = datetime.datetime.strptime(self.time, format)
                    break
                except ValueError:
                    if format == BackgroundTimer.ALLOWED_FORMATS[-1]:
                        raise BackgroundTimerError(
                            f"The time `{time}` does not match any recognized time format."
                        )
            now = datetime.datetime.now(zoneinfo.ZoneInfo(self.timezone))
            self.time = self.time.replace(year=now.year, month=now.month, day=now.day, tzinfo=zoneinfo.ZoneInfo(self.timezone))
            if self.time < datetime.datetime.now(zoneinfo.ZoneInfo(self.timezone)):
                self.time += datetime.timedelta(days=1)

    @property
    def delta(self) -> datetime.timedelta:
        if self.seconds is not None:
            return datetime.timedelta(
                seconds=self.seconds - (utcnow() - self.start).total_seconds()
            )
        return self.time - datetime.datetime.now(zoneinfo.ZoneInfo(self.timezone))

    async def task(self) -> None:
        await self.ctx.respond("Starting timer.")
        self.msg = await self.ctx.client.app.rest.create_message(self.channel_id, "__In Progress__\n```00:00:00```")
        self.start = utcnow()
        while True:
            if self.delta.total_seconds() <= 0:
                break
            await self.msg.edit(f"__In Progress__\n```{strfdelta(self.delta, '{%H}:{%M}:{%S}')}```")
            await asyncio.sleep(1)
        await self.msg.edit("__Time is up__\n```00:00:00```")
        await self.ctx.client.app.rest.create_message(self.channel_id, f"{self.ctx.user.mention}, the timer you set is up. DING A LING. 🔔")
