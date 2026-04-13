import hikari
import miru
from miru.ext import nav
import typing as t


def pagify(
        text: str,
        header='',
        footer='',
        delimiter=' ',
        limit_to=1900
    ) -> t.List[nav.Page]:
    pages = []
    sections = text.split(delimiter)
    current_text = ""
    for section in sections:
        if len(f"{header}{section}{delimiter}{footer}") > limit_to:
            raise ValueError(f"The text passed cannot be limited to {limit_to} based on the delimiter `{delimiter}`.")

        if len(f"{header}{current_text}{section}{delimiter}{footer}") <= limit_to:
            current_text += section + delimiter
        else:
            pages.append(nav.Page(content=f"{header}{current_text}{section}{delimiter}{footer}"))
            current_text = section + delimiter
    
    if current_text:
        pages.append(nav.Page(content=f"{header}{current_text}{delimiter}{footer}"))
    return pages


class LazyNavigatorView(nav.NavigatorView):
    def __init__(self, iterator):
        self.iterator = iterator
        pages = list(range(0, len(self.iterator)))
        super().__init__(pages=pages)
    
    async def send_page(self, context, page_index=None):
        if page_index is not None:
            self.current_page = page_index
        
        page = self.pages[self.current_page]
        page = await self.iterator.aget(page)
        page = page.get_embed()

        for item in self.children:
            await item.before_page_change()
        
        payload = self._get_page_payload(page)

        self._inter = context.interaction

        await context.edit_response(**payload)

    async def build_response_async(self, client, *, start_at=0, ephemeral=False):
        if self._client is not None:
            raise RuntimeError("Navigator is already bound to a client.")
        
        self.current_page = start_at
        self._ephemeral = ephemeral

        for item in self.children:
            await item.before_page_change()

        page = self.pages[start_at]
        observation = await self.iterator.aget(page)
        page = observation.get_embed()
        
        builder = miru.MessageBuilder(hikari.ResponseType.MESSAGE_CREATE, **self._get_page_payload(page))
        builder._client = client
        builder._view = self
        return builder
    






