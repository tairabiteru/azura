import hikari
import miru


class AuthorOnlyView(miru.View):
    def __init__(self, author: hikari.User, *args, **kwargs):
        self.author: hikari.User = author
        super().__init__(*args, **kwargs)
    
    async def view_check(self, context: miru.ViewContext) -> bool:
        if self.author.id != context.author.id:
            return False
        return True