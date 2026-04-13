import hikari
import koe
import lightbulb


class SessionError(koe.errors.KoeError):
    def __init__(self, message: str, internal: bool=False):
        super().__init__(message)
        self.internal = internal


@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
def require_user_in_voice(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context, cache: hikari.api.Cache) -> None:
    if ctx.user is None or ctx.guild_id is None:
        raise SessionError("ctx.user and ctx.guild_id cannot be None", internal=True)

    state = cache.get_voice_state(ctx.guild_id, ctx.user.id)

    if state is None:
        raise SessionError("You must be in a voice channel to use this command.")



@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
def require_existing_session(_: lightbulb.ExecutionPipeline, __: lightbulb.Context, session: koe.Session) -> None:
    if not session.exists:
        raise SessionError("I have to be connected to a voice channel to use this command.")


@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
def require_no_session(_: lightbulb.ExecutionPipeline, __: lightbulb.Context, session: koe.Session) -> None:
    if session.exists:
        raise SessionError("I'm already connected to a voice channel.")