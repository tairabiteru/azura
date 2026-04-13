import lightbulb

from ...core.conf import Config
from ...lib.hooks import require_granted
from ...mvc.core.db import dump_database


conf = Config.load()
database = lightbulb.Group("database", f"Commands related to {conf.name}'s database.")


@database.register
class Dump(
    lightbulb.SlashCommand,
    name="dump",
    description=f"Dumps {conf.name}'s entire database to a SQL file.",
    hooks=[require_granted]
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        fname = ctx.client.app.localnow().strftime('manual_backup_%Y_%m_%d_%H_%M_%S.sql')
        dump_database(fname)
        return await ctx.respond("Database backup was successful.")


@database.register
class Migrate(
    lightbulb.SlashCommand,
    name="migrate",
    description=f"Migrates {conf.name}'s database.",
    hooks=[require_granted]
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        pass