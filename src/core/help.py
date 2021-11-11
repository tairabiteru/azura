from core.conf import conf
from core.commands import SlashCommand, SlashCommandGroup, SlashSubGroup

import hikari


class Topic:
    def __init__(self, name, category, text):
        self.name = name
        self.category = category
        self._text = text
        TopicContainer.topics.append(self)

    @property
    def text(self):
        return self._text.format(bot=conf.name)

    @property
    def embed(self):
        embed = hikari.embeds.Embed(title=f"**{self.category} - {self.name}**")
        embed.description = self.text
        return embed


class SlashCommandTopic(Topic):
    def __init__(self, command):
        super().__init__(f"/{command.name}", "Slash Commands", command.help)
        self.command = command
        self.cog = self.command.node.split(".")[0]

    @property
    def text(self):
        return self._text.format(pre="/", name=self.name.replace("/", ""), node=self.command.node, bot=conf.name, grant_level=self.command._grant_level)

    @property
    def embed(self):
        embed = hikari.embeds.Embed(title=f"**{self.category} - {self.name}**")
        embed.description = self.text
        return embed


class SlashSubCommandTopic(SlashCommandTopic):
    def __init__(self, group, command):
        super().__init__(command)
        self.name = f"/{group.name} {command.name}"
        self.group = group


class SlashSubGroupTopic(SlashSubCommandTopic):
    def __init__(self, group, subgroup):
        super().__init__(group, subgroup)
        self.name = f"/{group.name} {subgroup.name}"
        self.group = group
        self.subgroup = subgroup

    @property
    def text(self):
        try:
            return self._text.format(pre="/", name=self.name.replace("/", ""), node=self.command.node, bot=conf.name, grant_level=self.command._grant_level)
        except AttributeError:
            return self._text.format(pre="/", name=self.name.replace("/", ""), node=self.command.node, bot=conf.name)


class SlashSubGroupCommandTopic(SlashCommandTopic):
    def __init__(self, group, subgroup, command):
        super().__init__(command)
        self.name = f"/{group.name} {subgroup.name} {command.name}"


class CommandTopic(Topic):
    def __init__(self, command):
        super().__init__(command.name, "Commands", command.help)
        self.command = command

    @property
    def text(self):
        return self._text.format(pre=conf.prefix, name=self.name.replace("/", ""), node=self.command.node, bot=conf.name, grant_level=self.command._grant_level)

    @property
    def embed(self):
        embed = hikari.embeds.Embed(title=f"**{self.category} - {conf.prefix}{self.name}**")
        embed.description = self.text
        return embed


class TopicContainer:
    topics = []

    def __init__(self):
        pass

    @classmethod
    def build(cls, bot):
        for command in bot.slash_commands:
            if isinstance(command, SlashCommand):
                try:
                    SlashCommandTopic(command)
                except AttributeError:
                    pass
            elif isinstance(command, SlashCommandGroup):
                try:
                    SlashCommandTopic(command)
                except AttributeError:
                    pass
                for subcommand in command._subcommands.values():
                    if isinstance(subcommand, SlashSubGroup):
                        try:
                            SlashSubGroupTopic(command, subcommand)
                        except AttributeError:
                            pass
                        for subsubcommand in subcommand._subcommands.values():
                            try:
                                SlashSubGroupCommandTopic(command, subcommand, subsubcommand)
                            except AttributeError:
                                pass
                    else:
                        try:
                            SlashSubCommandTopic(command, subcommand)
                        except AttributeError:
                            pass

        for command in bot.commands:
            try:
                CommandTopic(command)
            except AttributeError:
                pass
        return cls()

    @property
    def categories(self):
        categories = []
        for topic in TopicContainer.topics:
            if topic.category not in categories:
                categories.append(topic.category)
        return categories

    @property
    def embed(self):
        embed = hikari.embeds.Embed(title="__Help Topics__")
        for cog in sorted(self.getCogs()):
            title = cog.capitalize()
            value = "`, `".join(sorted([topic.name for topic in self.getTopicsInCog(cog)]))
            embed.add_field(name=f"**[Slash Commands/{title}]**", value=f"`{value}`")
        for category in self.categories:
            if category != "Slash Commands":
                value = "`, `".join(sorted([topic.name for topic in self.getTopicsInCategory(category)]))
                embed.add_field(name=f"**[{category}]**", value=f"`{value}`")
        return embed

    def getTopicsInCategory(self, category):
        topics = []
        for topic in TopicContainer.topics:
            if topic.category == category:
                topics.append(topic)
        return topics

    def getTopicsInCog(self, cog):
        topics = []
        for topic in TopicContainer.topics:
            if topic.category == "Slash Commands":
                if topic.cog == cog:
                    topics.append(topic)
        return topics

    def getCogs(self):
        cogs = []
        for topic in TopicContainer.topics:
            if topic.category == "Slash Commands":
                if topic.cog not in cogs:
                    cogs.append(topic.cog)
        return cogs

    def getTopic(self, topic):
        for t in TopicContainer.topics:
            if t.name.lower() == topic.lower() or t.name.lower().replace("/", "") == topic.lower():
                return t
