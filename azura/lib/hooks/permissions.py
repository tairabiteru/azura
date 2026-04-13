import lightbulb

from ..permissions import eval_allowed, eval_not_denied, AccessIsDenied
from ...mvc.discord.models import User


async def stage_permissions_objects(ctx):
    user, _ = await User.objects.aget_or_create(id=ctx.user.id)
    acl = await user.get_acl(ctx.client.app.permissions_root)
    node = ctx.client.app.permissions_root.get_node_from_command(ctx.command)
    return acl, node


@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
async def require_granted(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context) -> None:
    acl, node = await stage_permissions_objects(ctx)
    if not eval_allowed(node, acl):
        raise AccessIsDenied(ctx, "You lack the required permissions to run this command.")
    

@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
async def require_not_denied(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context) -> None:
    acl, node = await stage_permissions_objects(ctx)
    if not eval_not_denied(node, acl):
        raise AccessIsDenied(ctx, "You have been denied the ability to run this command.")


@lightbulb.hook(lightbulb.ExecutionSteps.CHECKS)
async def require_owner(_: lightbulb.ExecutionPipeline, ctx: lightbulb.Context) -> None:
    if ctx.user.id != ctx.client.app.conf.owner_id:
        raise AccessIsDenied(ctx, "Only my owner can run this command.")
    
    
