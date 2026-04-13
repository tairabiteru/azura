import lightbulb

from ...core.conf import Config


conf = Config.load()
tools = lightbulb.Loader()


@tools.command
class Ping(
    lightbulb.SlashCommand,
    name="ping",
    description=f"See if {conf.name} is alive."
):

    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context):
        await ctx.respond("PONG! 🏓")


@tools.command
class Help(
    lightbulb.SlashCommand,
    name="help",
    description=f"Explain various parts of {conf.name}."
):
    
    topic = lightbulb.string("topic", "The topic to get help with.")

    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context):
        pass