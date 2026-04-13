import koe


def get_voice_state_for_user(bot, user):
    for guild, user_state in bot.cache.get_voice_states_view().items():
        for u, state in user_state.items():
            if u == user:
                return guild, state
    return None, None


async def get_session_or_none_from_uid(bot, user) -> koe.Session | None:
    guild, state = get_voice_state_for_user(bot, user)
    
    if guild is None:
        return None
    if state is None:
        return None
    
    return await bot.koe.get_session_or_none_by(guild_id=guild)