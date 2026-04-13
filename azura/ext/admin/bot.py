import hikari
import lightbulb
from miru.ext import nav
import os
import platform
import sys

from ...core.conf import Config
from ...lib.utils import strfdelta, get_byte_unit, get_dir_size, aio_get
from ...lib.components import validate, pagify
from ...lib.ctx import DelayedResponse


conf = Config.load()
bot = lightbulb.Group("bot", f"Commands related to {conf.name}.")


@bot.register
class Uptime(
    lightbulb.SlashCommand,
    name="uptime",
    description="Display uptime information."
):
    
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        embed = hikari.Embed(title=f"{conf.name}'s Current Uptime")
        inst = f"@{ctx.client.app.last_instantiation.strftime('%x %X %Z')}, "
        inst += f"{strfdelta(ctx.client.app.localnow() - ctx.client.app.last_instantiation, '{%H}:{%M}:{%S}')} elapsed"
        embed.add_field("Instantiation", value=inst)
        api = f"@{ctx.client.app.last_connection.strftime('%x %X %Z')}, "
        api += f"{strfdelta(ctx.client.app.localnow() - ctx.client.app.last_connection, '{%H}:{%M}:{%S}')} elapsed"
        embed.add_field("API Contact", value=api)
        return await ctx.respond(embed)


@bot.register
class Kill(
    lightbulb.SlashCommand,
    name="kill",
    description=f"Kill {conf.name}."
):
    warning = f"You are about to send a kill signal. Upon doing so,\
        {conf.name} wll cease to work entirely, and this action can \
        only be reversed with console access. Are you sure you wish to\
        do this?"
    
    @validate(warning)
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:    
        await ctx.client.app.close(ctx=ctx, kill=True)


@bot.register
class Reinit(
    lightbulb.SlashCommand,
    name="reinit",
    description=f"Restart {conf.name}."
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        await ctx.client.app.close(ctx=ctx)


@bot.register
class Logs(
    lightbulb.SlashCommand,
    name="logs",
    description=f"View {conf.name}'s logs."
):
    type = lightbulb.string(
        "type",
        "The log type to view.",
        default="bot",
        choices=[
            lightbulb.Choice("bot", "bot"),
            lightbulb.Choice("access", "access")
        ]
    )

    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        try:
            with open(os.path.join(conf.logs, f"{self.type}.log"), "r") as logfile:
                lines = await logfile.read()
        except FileNotFoundError:
            return await ctx.respond(f"No {self.type} logs available.")

        pages = pagify(lines, header='```', footer='```', delimiter='\n', limit_to=1600)
        navigator = nav.NavigatorView(pages=pages)
        builder = await navigator.build_response_async(ctx.client.app.miru)
        await builder.create_initial_response(ctx.interaction)
        ctx.client.app.miru.start_view(navigator)


@bot.register
class Info(
    lightbulb.SlashCommand,
    name="info",
    description="View information."
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        latency = round((ctx.client.app.heartbeat_latency * 1000), 1)
        frequency = round(1000.0 / latency, 5)
        python_version = ".".join(map(str, sys.version_info[0:3]))

        embed = hikari.Embed(title=conf.name, url=f"https://{conf.mvc.allowed_hosts[0]}")
        embed.description = f"**Version {ctx.client.app.version}**\nRunning on {platform.python_implementation()} {python_version}"
        embed.set_thumbnail(ctx.client.app.get_me().avatar_url)

        root = get_byte_unit(get_dir_size(conf.root))
        temp = get_byte_unit(get_dir_size(conf.temp))
        logs = get_byte_unit(get_dir_size(conf.logs))
        dirs = f"Root: {root}\nTemp: {temp}\nLogs: {logs}"
        embed.add_field("Directory Info", value=dirs)

        heartbeat_info = f"Period: {latency} ms\nFrequency: {frequency} Hz"
        embed.add_field("Heartbeat Info", value=heartbeat_info)
        await ctx.respond(embed)


@bot.register
class IP(
    lightbulb.SlashCommand,
    name="ip",
    description=f"View {conf.name}'s TCP/IP connection information.",
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        
        async with DelayedResponse(ctx, "Obtaining TCP/IP info...", timeout=10) as response:
            ip = await aio_get("https://api.ipify.org")
            embed = hikari.Embed(title="TCP/IP Information")
            embed.add_field("IP Address", ip)
            return await response.complete("", embed=embed)