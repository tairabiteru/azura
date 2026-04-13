"""
Injection functions for the ORM.

These functions are all designed to work with Lightbulb 3's
DI system. Their purpose is to, given a context, retrieve an object
from the database associated with that object.
"""
import lightbulb

from azura.mvc.discord.models import User, Channel, Guild


async def get_user(ctx: lightbulb.Context) -> User:
    return await User.objects.aget(id=ctx.user.id)


async def get_guild(ctx: lightbulb.Context) -> Guild:
    return await Guild.objects.aget(id=ctx.guild_id)


async def get_channel(ctx: lightbulb.Context) -> Channel:
    return await Channel.objects.aget(id=ctx.channel_id)
