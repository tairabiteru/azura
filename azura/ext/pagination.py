import hikari
import miru


class PageRevButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⬅️")

    async def callback(self, ctx):
        await self.view.change_page(ctx, self.view.page-1)


class PageAdvButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="➡️")

    async def callback(self, ctx):
        await self.view.change_page(ctx, self.view.page+1)


class PageStartButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⏪")

    async def callback(self, ctx):
        await self.view.change_page(ctx, 0)


class PageEndButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⏩")

    async def callback(self, ctx):
        await self.view.change_page(ctx, len(self.view.pages)-1)


class PaginatedView(miru.View):
    def __init__(self, pages, *args, page=0, **kwargs):
        self.pages = pages
        self.page = page

        super().__init__(*args, **kwargs)
        self.update_buttons()

    async def change_page(self, ctx, page):
        self.page = page
        self.update_buttons()
        await ctx.edit_response(self.current, components=self.build())

    @property
    def current(self):
        return self.pages[self.page]

    def update_buttons(self):
        self.clear_items()

        if self.page != 0:
            self.add_item(PageStartButton())
            self.add_item(PageRevButton())
        if self.page != len(self.pages)-1:
            self.add_item(PageAdvButton())
            self.add_item(PageEndButton())

    def build(self):
        try:
            return super().build()
        except ValueError:
            return []
