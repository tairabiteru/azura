import hikari
import lightbulb
import typing as t

from ...core.bot import Bot


class Context(lightbulb.Context):    
    @property
    def bot(self) -> Bot:
        return t.cast(Bot, self.client.app)
    
    @property
    def guild_id(self) -> hikari.Snowflake:
        id = super(Context, self).guild_id
        assert id is not None
        return id
    
    @property
    def voice_id(self) -> hikari.Snowflake | None:
        state = self.bot.cache.get_voice_state(self.guild_id, self.user.id)
        
        if not state or not state.channel_id:
            return None
        
        return state.channel_id


async def get_context(ctx: lightbulb.Context) -> Context:
    ctx = Context(
        ctx.client,
        ctx.interaction,
        ctx.options,
        ctx.command,
        ctx.initial_response_sent
    )
    await ctx.command._resolve_options()
    return ctx