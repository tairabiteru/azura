import hikari
import miru

from .base import AuthorOnlyView
from ..utils import utcnow
from ...mvc.genshin.models import GenshinSettings


class ClaimTransientButton(miru.Button):
    def __init__(self, settings: GenshinSettings, position: int):
        self.settings: GenshinSettings = settings

        super().__init__(
            label="Claim ",
            emoji=GenshinSettings.TRANSIENT_EMOJI,
            style=hikari.ButtonStyle.PRIMARY,
            position=position
        )
    
    async def callback(self, ctx):
        self.settings.last_transient_obtained_at= utcnow()
        await self.settings.asave() 
        await self.view.update(ctx)


class ClaimRealmCurrencyButton(miru.Button):
    def __init__(self, settings: GenshinSettings, position: int):
        self.settings: GenshinSettings = settings

        super().__init__(
            label="Claim ",
            emoji=GenshinSettings.REALM_CURRENCY_EMOJI,
            style=hikari.ButtonStyle.PRIMARY,
            position=position
        )
    
    async def callback(self, ctx):
        self.settings.realm_currency_drained_at = utcnow()
        await self.settings.asave() 
        await self.view.update(ctx)


class GenshinMenu(AuthorOnlyView):
    def __init__(self, author: hikari.User, settings: GenshinSettings, timeout: int=None):
        super().__init__(author, timeout=timeout)
        self.settings = settings

        self.add_item(ClaimRealmCurrencyButton(self.settings, 0))

        if self.settings.can_obtain_transient:
            self.add_item(ClaimTransientButton(self.settings, 1))
    
    async def update(self, ctx: miru.ViewContext):
        self.stop()
        view = self.__class__(self.author, self.settings, timeout=self.timeout)
        embed = await self.settings.get_timers_embed(ctx.client.app, ctx.author)
        await ctx.edit_response(embed, components=view)
        ctx.client.app.miru.start_view(view)