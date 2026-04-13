import anytree
import lightbulb

from ...core.conf import Config
from ...lib.hooks import require_granted


conf = Config.load()
permissions = lightbulb.Group("permissions", f"Commands to manage {conf.name}'s command permissions.")


@permissions.register
class Set(
    lightbulb.SlashCommand,
    name="set",
    description="Set permissions for an object.",
    hooks=[require_granted]
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        pass


@permissions.register
class ACL(
    lightbulb.SlashCommand,
    name="acl",
    description="View the permissions ACL for an object."
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        pass


@permissions.register
class Tree(
    lightbulb.SlashCommand,
    name="tree",
    description=f"View {conf.name}'s permissions tree."
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        await ctx.respond(
            f"```{anytree.RenderTree(ctx.client.app.permissions_root)}```"
        )