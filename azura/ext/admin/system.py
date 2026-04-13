import asyncio
import hikari
import lightbulb
import platform
import psutil

from ...core.conf import Config
from ...lib.utils import get_byte_unit
from ...lib.ctx import DelayedResponse


system = lightbulb.Group("system", "Commands related to the system.")
conf = Config.load()


@system.register
class CPU(
    lightbulb.SlashCommand,
    name="cpu",
    description="Display system CPU information."
):
    interval = lightbulb.integer("interval", "The time period over which to observe the CPU.", default=1)

    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        if self.interval > 15 or self.interval < 1:
            return await ctx.respond("CPU utilization interval must be between 1 and 15.")
    
        plural = "second" if self.interval == 1 else "seconds"
        embed = hikari.Embed(title=f"**{platform.node().capitalize()} - CPU Utilization**")
        freq = psutil.cpu_freq()
        freq = f"```MINIMUM: {round(freq.min)} MHz\nMAXIMUM: {round(freq.max)} MHz\nCURRENT: {round(freq.current)} MHz\n```"
        embed.add_field(name="Frequency", value=freq, inline=True)

        load_avg = [avg / psutil.cpu_count() * 100 for avg in psutil.getloadavg()]
        load_avg = f"```T-060: {round(load_avg[0], 2)}%\nT-300: {round(load_avg[1], 2)}%\nT-900: {round(load_avg[2], 2)}%```"
        embed.add_field(name="Load Averages", value=load_avg, inline=True)

        async with DelayedResponse(ctx, f"Observing CPU utilization over {self.interval} {plural}", timeout=self.interval+1) as response:
            psutil.cpu_percent(percpu=True)
            await asyncio.sleep(self.interval)
            loads = psutil.cpu_percent(percpu=True)
            cpu_loads = "```"
            cpu_loads += f"CORE-[AVG]: {round(sum(loads) / len(loads), 2)}%\n"
            cpu_loads += f"CORE-[MIN]: {min(loads)}%\n"
            cpu_loads += f"CORE-[MAX]: {max(loads)}%\n"
            cpu_loads += "----------------------------\n"
            for i, load in enumerate(loads):
                i = i if i > 0 else f"0{i}"
                cpu_loads += f"CORE-[{i}]: {load}%\n"
            embed.add_field(name="Core Loads", value=f"{cpu_loads}```")
            return await response.complete(f"CPU Utilization over {self.interval} {plural}", embed=embed)


@system.register
class Disks(
    lightbulb.SlashCommand,
    name="disks",
    description="Display system disk information."
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        embed = hikari.Embed(title=f"**{platform.node().capitalize()} - Disk Utilization**")
        for disk in conf.vars.system_cmd_disks:
            usage = psutil.disk_usage(disk)
            info = f"```-- {usage.percent}% --\nFREE: {get_byte_unit(usage.free)}\nUSED: {get_byte_unit(usage.used)}\n TOTAL: {get_byte_unit(usage.total)}```"
            embed.add_field(name=disk, value=info)
        return await ctx.respond(embed)


@system.register
class Network(
    lightbulb.SlashCommand,
    name="network",
    description="Display system network information."
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        embed = hikari.Embed(title=f"**{platform.node().capitalize()} - Network Utilization**")
        network_io = psutil.net_io_counters()
        embed.add_field(name="Bytes Tx", value=get_byte_unit(network_io.bytes_sent), inline=True)
        embed.add_field(name="Bytes Rx", value=get_byte_unit(network_io.bytes_recv), inline=True)
        embed.add_field(name="Packets Tx", value="{:,}".format(network_io.packets_sent))
        embed.add_field(name="Packets Rx", value="{:,}".format(network_io.packets_recv))
        return await ctx.respond(embed)
    

@system.register
class Ram(
    lightbulb.SlashCommand,
    name="ram",
    description="Display system RAM information."
):
    @lightbulb.invoke
    async def invoke(self, ctx: lightbulb.Context) -> None:
        embed = hikari.Embed(title=f"**{platform.node().capitalize()} - Memory Utilization**")
        memory = psutil.virtual_memory()
        embed.description = f"Percentage Used: {memory.percent}%"
        embed.add_field(name="Available", value=get_byte_unit(memory.available), inline=True)
        embed.add_field(name="In Use", value=get_byte_unit(memory.total - memory.available), inline=True)
        return await ctx.respond(embed)