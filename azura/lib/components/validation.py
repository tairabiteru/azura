from functools import wraps
import hikari
import lightbulb
import miru
import typing as t

from .base import AuthorOnlyView


class ValidationButton(miru.Button):
    def __init__(self, label: str, style: hikari.ButtonStyle, value) -> None:
        super().__init__(label, style=style)
        self.view: Validation
        self.value = value
    
    async def callback(self, _: miru.ViewContext) -> None:
        self.view.validated = self.value


class Validation(AuthorOnlyView):
    def __init__(self, author: hikari.User, confirm: str, cancel: str, timeout=None) -> None:
        super().__init__(author, timeout=timeout)
        self.validated: t.Optional[bool] = None
        self.add_item(ValidationButton(confirm, style=hikari.ButtonStyle.SECONDARY, value=True))
        self.add_item(ValidationButton(cancel, style=hikari.ButtonStyle.PRIMARY, value=False))


def validate(
        warning: t.Optional[str] = None,
        title: t.Optional[str] = "Confirmation",
        confirm: str = "Yes",
        cancel: str = "No",
        ephemeral: bool = False,
        timeout: t.Optional[int] = 30
):
    def decorator(func: callable):
        @wraps(func)
        async def wrapper(self: lightbulb.CommandBase, ctx: lightbulb.Context, *args, **kwargs) -> None:
            embed = hikari.Embed(
                title=title,
                description=warning,
            )
            view = Validation(ctx.user, confirm, cancel, timeout=timeout)

            resp = await ctx.respond(embed, components=view, ephemeral=ephemeral)
            ctx.client.app.miru.start_view(view)
            await view.wait_for_input()

            await ctx.delete_response(resp)

            if view.validated is True:
                await func(self, ctx, *args, **kwargs)
            else:
                await ctx.edit_response(resp, "Operation cancelled.")
        
        return wrapper

    return decorator