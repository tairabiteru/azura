from libs.core.conf import settings

from discord.ext import commands
import discord

class Help(commands.HelpCommand):

    COLOR = discord.Color.blurple()

    def get_ending_note(self):
        return 'Use {0}{1} [command] for more information on a command.'.format(self.clean_prefix, self.invoked_with)

    def get_command_signature(self, command):
        return '{0}{1.qualified_name} {1.signature}'.format(settings['bot']['commandPrefix'], command)

    async def send_bot_help(self, mapping):
        embed = discord.Embed(title='Bot Commands', color=self.COLOR)
        description = self.context.bot.description
        if description:
            embed.description = description

        for cog, commands in mapping.items():
            name = 'No Category' if cog is None else cog.qualified_name
            filtered = await self.filter_commands(commands, sort=True)
            if filtered:
                value = '\u2002'.join(c.name for c in commands)
                if cog and cog.description:
                    value = '{0}\n{1}'.format(cog.description, value)
            embed.add_field(name=name, value="`" + "`, `".join(sorted([command.qualified_name for command in commands])) + "`", inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_cog_help(self, cog):
        embed = discord.Embed(title='{0.qualified_name} Commands'.format(cog), color=self.COLOR)
        if cog.description:
            embed.description = cog.description

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            embed.add_field(name=self.get_command_signature(command), value=command.short_doc or '...', inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        embed = discord.Embed(title=settings['bot']['commandPrefix'] + group.qualified_name, color=self.COLOR)

        if isinstance(group, commands.Group):
            filtered = await self.filter_commands(group.commands, sort=True)
            for command in filtered:
                doc = command.short_doc or '...'
                if doc != '...':
                    doc = doc.format(pre=settings['bot']['commandPrefix'], aliases="`, `".join(list([settings['bot']['commandPrefix'] + alias for alias in command.aliases])))
                embed.add_field(name=self.get_command_signature(command), value=doc, inline=False)

        if isinstance(group, commands.Command):
            command = group
            if command.help:
                aliases = "`, `".join(list([settings['bot']['commandPrefix'] + alias for alias in command.aliases])) if command.aliases else "None"
                desc = command.help
                desc = desc.format(pre=settings['bot']['commandPrefix'], command_name=command.qualified_name, aliases=aliases, node=command.node(self.context.bot), grant_level=command.grant_level, bot=settings['bot']['name'].capitalize())
                embed.description = desc

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    send_command_help = send_group_help
