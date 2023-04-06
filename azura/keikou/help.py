from core.conf import conf

import hikari
import miru
import toml


COMMAND_TEMPLATE = "**Syntax**: `/{signature}`\n**Node**: `{node}`\n**Grant Level**: `{grant_level}`\n\n**__Description__**\n{description}\n\n**__Options__**\n{options}"
GROUP_TEMPLATE = "**Node**: `{node}`\n\n**__Description__**\n{description}\n\n**__Commands__**\n{commands}"


TYPING_MAP = {
    str: 'String',
    int: 'Integer',
    float: 'Decimal',
    bool: 'Boolean',
    hikari.User: 'User',
    hikari.Snowflake: 'Snowflake'
}


class TopicSelect(miru.Select):
    def __init__(self, topic, *args, **kwargs):
        self.topic = topic

        options = []
        if self.topic.subtopics:
            for topic in self.topic.subtopics:
                options.append(miru.SelectOption(topic.title()))
        kwargs['options'] = options
        super().__init__(*args, **kwargs)

    async def callback(self, ctx):
        topic = self.topic.getSubTopic(self.values[0])
        menu = TopicMenu(topic)
        components = menu.build() if topic.subtopics != [] else []
        await ctx.edit_response(topic.embed, components=components)
        menu.start(ctx.message)
        await menu.wait()


class TopicMenu(miru.View):
    def __init__(self, topic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(TopicSelect(topic))


class Topic:
    def __init__(self, title, text, category=None, subtopics=[]):
        self._title = title
        self._text = text
        self.category = category
        self.subtopics = subtopics

    def text(self):
        if callable(self._text):
            return self._text()
        return self._text

    def title(self):
        if callable(self._title):
            return self._title()
        return self._title

    def getSubTopic(self, title):
        for topic in self.subtopics:
            if topic.title() == title:
                return topic

    @property
    def embed(self):
        if self.category is not None:
            embed = hikari.embeds.Embed(title=f"{self.category} - {self.title()}")
        else:
            embed = hikari.embeds.Embed(title=self.title())
        embed.description = self.text()
        return embed


class CommandTopic(Topic):
    def __init__(self, command):
        self.command = command
        super().__init__(self.title, self.helptext, "Commands", subtopics=[])

    def title(self):
        return f"/{self.command.qualname}"

    @property
    def options(self):
        text = ""
        for option in self.command.options.values():
            type = TYPING_MAP[option.arg_type] if option.choices is None else "Enumeration"
            text += f"`{option.name}` ({str(type)}) - {option.description}\n"
        text = text if text != "" else "This command has no options."
        return text

    def helptext(self):
        docstring = f"\n{self.command.callback.__doc__}" if self.command.callback.__doc__ else ""
        text = COMMAND_TEMPLATE.format(signature=self.command.signature, node=self.command.node, grant_level=self.command.grant_level.value, description=f"{self.command.description}{docstring}", options=self.options)
        return text


class GroupTopic(Topic):
    def __init__(self, group):
        self.group = group
        super().__init__(self.title, self.helptext, "Commands", subtopics=[])

        for command in sorted(self.group.subcommands.values(), key=lambda c: c.node):
            if not hasattr(command, "subcommands"):
                self.subtopics.append(CommandTopic(command))
            else:
                self.subtopics.append(GroupTopic(command))

    @property
    def commands(self):
        text = ""
        for command in sorted(self.group.subcommands.values(), key=lambda c: c.node):
            if hasattr(command, "subcommands"):
                for subcommand in command.subcommands.values():
                    text += f"`/{subcommand.qualname}` - {subcommand.description}\n"
            else:
                text += f"`/{command.qualname}` - {command.description}\n"
        return text

    def title(self):
        return f"/{self.group.qualname}"

    def helptext(self):
        docstring = f"\n{self.group.callback.__doc__}" if self.group.callback.__doc__ else ""
        text = GROUP_TEMPLATE.format(node=self.group.node, description=f"{self.group.description}{docstring}", commands=self.commands)
        return text


class PluginTopic(Topic):
    def __init__(self, plugin):
        self.plugin = plugin
        super().__init__(f"{self.plugin.name.capitalize()} Plugin", self.helptext, "Plugins", subtopics=[])

        for command in sorted(self.plugin.all_commands, key=lambda c: c.node):
            if not hasattr(command, "subcommands"):
                self.subtopics.append(CommandTopic(command))
            else:
                self.subtopics.append(GroupTopic(command))

    @property
    def commands(self):
        text = ""
        for command in sorted(self.plugin.all_commands, key=lambda c: c.node):
            text += f"`/{command.qualname}` - {command.description}\n"
        return text

    def helptext(self):
        text = GROUP_TEMPLATE.format(node=self.plugin.node, description=self.plugin.description, commands=self.commands)
        return text


class DisambiguationTopic(Topic):
    def __init__(self, topics):
        self.topics = topics
        super().__init__("Disambiguation", self.helptext(), None, subtopics=self.topics)

    def helptext(self):
        text = ""
        for topic in self.topics:
            text += f"`{topic.title()}`\n"
        return text


class HelpTopic(Topic):
    def __init__(self, bot):
        super().__init__("Main Help Menu", "Main menu for help.")
        self.bot = bot
        self.permissions = None

        try:
            with open("faq.toml", "r") as faqfile:
                faqdata = toml.load(faqfile)
        except FileNotFoundError:
            f = open("faq.toml", "w")
            f.close()
            faqdata = {}

        self.permissions = self.bot.permissions

        plugins = Topic("Plugins", f"Plugins are components of {conf.parent.name} which organize commands into compartments.\n\n", subtopics=[])
        faq = Topic("FAQ", "General topics, and questions that are often asked.", subtopics=[])

        for plugin in sorted(self.bot.plugins.values(), key=lambda p: p.name):
            plugins._text += f"**{plugin.name}** - {plugin.description}\n\n"
            plugins.subtopics.append(PluginTopic(plugin))

        for title, desc in faqdata.items():
            text = desc['text']
            mapping = {
                'botname': conf.parent.name,
                'outfacingURL': conf.dash.outfacing_url
            }
            text = text.format_map(mapping)
            faq.subtopics.append(Topic(title, text, "FAQ", subtopics=[]))

        self.subtopics.append(plugins)
        self.subtopics.append(faq)

    def recursiveGetTopics(self, topics):
        all_topics = []
        for topic in topics:
            all_topics.append(topic)
            if topic.subtopics != []:
                all_topics += self.recursiveGetTopics(topic.subtopics)
        return all_topics

    def resolveByTopicName(self, name):
        for topic in self.subtopics:
            if topic.title() == name:
                return topic

    def recursiveNodeSearch(self, topic, node):
        for subtopic in topic.subtopics:
            if isinstance(subtopic, CommandTopic):
                if subtopic.command.node == node:
                    return node
            else:
                if subtopic.group.node == node:
                    return subtopic
                return self.recursiveNodeSearch(subtopic, node)

    def resolveByNode(self, node):
        plugins = self.resolveByTopicName("Plugins")
        for topic in plugins.subtopics:
            if topic.plugin.node == node:
                return topic
            rec_topic = self.recursiveNodeSearch(topic, node)
            if rec_topic is not None:
                return rec_topic

    def resolveTopic(self, query):
        if query is None:
            return self

        topic = self.resolveByNode(query)
        if topic is not None:
            return topic

        possible_topics = []
        for topic in self.recursiveGetTopics(self.subtopics):
            if query.lower() in topic.title().lower():
                possible_topics.append(topic)

        if len(possible_topics) == 1:
            return possible_topics[0]
        elif len(possible_topics) > 1:
            return DisambiguationTopic(possible_topics)
