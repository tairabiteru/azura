"""
Injection functions for the ORM.

These functions are all designed to work with Lightbulb 3's
DI system. Their purpose is to, given a context, retrieve an object
from the database associated with that object.
"""
import koe
from .ctx import Context


async def get_session(ctx: Context) -> koe.Session:
    session = await ctx.bot.koe.get_session_or_none_by(guild_id=ctx.guild_id)
    
    if session is not None:
        return session
    
    return koe.Session(ctx.bot.koe)
