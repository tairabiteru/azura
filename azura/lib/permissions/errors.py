import lightbulb


class PermissionsError(Exception):
    pass


class NodeNotFound(PermissionError):
    pass


class AccessIsDenied(PermissionError):
    def __init__(self, ctx: lightbulb.Context, reason: str):
        self.reason = reason
        self.ctx = ctx
    
    @property
    def message(self) -> str:
        return f"**Access is denied**: {self.reason}"
    
    async def respond(self):
        await self.ctx.respond(self.message)
    
