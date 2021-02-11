"""Module containing all issue tracking commands."""

from libs.core.conf import conf
from libs.core.permissions import command
from libs.ext.pagination import paginate_embed
from libs.ext.utils import localnow
from libs.orm.issues import Issues as IssuesMaster

import discord
from discord.ext import commands


class Issues(commands.Cog):
    """Cog containing all issue tacking commands."""

    def __init__(self, bot):
        """Initialize issues cog."""
        self.bot = bot

    @command(grant_level="explicit", aliases=['iopen', 'issueadd'])
    async def issueopen(self, ctx, *, entry=None):
        """
        Syntax: `{pre}{command_name} <title>|[description]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Opens an issue in {bot}'s internal issue tracker.
        When writing in an entry, you should specify the title first.
        The description is optional, however if you want to specify it, you can
        separate it from the title with a `|`.

        __**Arguments**__
        `<title>` - The title of the issue.
        `|[description]` - The description of the issue. It is separated from the
        title by a `|`.

        __**Example Usage**__
        `{pre}{command_name} Bot's broken.`
        `{pre}{command_name} This is an issue title | and this is the description.`
        """
        if entry is None:
            return await ctx.send("You must provide a title and optionally, a description:\n`{pre}issueopen My Title | My description`".format(pre=conf.prefix))
        entry = entry.split("|")
        if len(entry) == 1:
            entry.append("No description provided.")
        elif len(entry) != 2:
            entry = [entry[0], ''.join(entry[1:])]
        title, desc = entry
        issues = IssuesMaster.obtain()
        issue = issues.open(title, description=desc)
        return await ctx.send("Issue added with ID #{id}.".format(id=issue.id))

    @command(grant_level="explicit", aliases=['il'])
    async def issuelist(self, ctx, tag_or_id="open"):
        """
        Syntax: `{pre}{command_name} [tag_or_id]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Lists issues. A `#tag` may be specified for all issues matching that
        tag, or an issue number can be specified to list the details about
        a specific issue. If neither are specified it defaults to all open
        issues.

        __**Arguments**__
        `[tag_or_id]` - The tag or ID number. All matching tags will be shown
        whereas only the single matching issue will be shown when a number
        is specified. If not given, all open issues are displayed.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} #critical`
        `{pre}{command_name} 69`
        """
        if tag_or_id.isdigit():
            id = int(tag_or_id)
            try:
                issue = IssuesMaster.obtain(id=id)
            except KeyError:
                return await ctx.send("No issue with ID #{id} exists.".formaT(id=id))
            embed = discord.Embed(title="__Issue #{id}__".format(id=id), description=issue.title, color=0xc6c6c6)
            embed.add_field(name="__Tags__", value="`{tags}`".format(tags="`, `".join(issue.status_tags)), inline=True)
            embed.add_field(name="__Date Created__", value=issue.date.strftime("%-m/%-d/%Y %-I:%M:%S %p %Z"), inline=True)
            embed.add_field(name="__Description__", value=issue.description, inline=True)
            responses = list([response.render(ctx.guild) for response in issue.responses])
            resp_title = "Responses in chronological order:" if responses else "No responses yet."
            embed.add_field(name="__Responses__", value=resp_title, inline=True)
            await paginate_embed(ctx, embed, responses, threshold=900)
        else:
            tag = tag_or_id.lower()
            if tag.replace("#", "") == "all":
                title = "__All Issues__"
                matches = list([match for id, match in IssuesMaster.obtain().issues.items()])
            else:
                if tag.replace("#", "") not in conf.issues.validTags:
                    return await ctx.send("Invalid tag specified: `{tag}`. Valid tags are `{tags}`.".format(tag=tag, tags="`, `".join(conf.issues.validTags)))
                matches = list([match for id, match in IssuesMaster.obtain(tag=tag).items()])
            if len(matches) == 0:
                return await ctx.send("No issues with tags matching `#{tag}` were found.".format(tag=tag.replace("#", "")))
            title = "__Issues with tag {tag}__".format(tag=tag) if tag.startswith("#") else "__Issues with tag #{tag}__".format(tag=tag)
            description = "{matches} as of {time}".format(matches="{:,}".format(len(matches)), time=localnow().strftime("%-m/%-d/%Y %-I:%M:%S %p"))
            embed = discord.Embed(title=title, description=description, color=0xc6c6c6)
            pack = list([["#{id} - {tags}".format(id=issue.id, tags=issue.rendered_tags), issue.title] for issue in matches])
            await paginate_embed(ctx, embed, pack, threshold=900)

    @command(grant_level="explicit", aliases=['ir'])
    async def issuerespond(self, ctx, id=None, *, response):
        """
        Syntax: `{pre}{command_name} <id> <response>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Respond to the issue with the specified ID.

        __**Arguments**__
        `<id>` - The ID number of the issue to respond to.
        `<response>` - The response to the issue.

        __**Example Usage**__
        `{pre}{command_name} 69 This is my response.`
        """
        if id is None:
            return await ctx.send(f"You must specify the ID:\n{conf.prefix}issuerespond <id> <response>")
        if not id.isdigit():
            return await ctx.send("Invalid ID number: `{id}`.".format(id=id))
        try:
            issue = IssuesMaster.obtain(id=int(id))
        except KeyError:
            return await ctx.send("No issue with the ID `{id}` exists.".format(id=id))
        issues = IssuesMaster.obtain()
        if "#acknowledged" not in issue.status_tags:
            issue.status_tags.append("#acknowledged")
        issue.add_response(author=ctx.author.id, response=response)
        issues.issues[str(issue.id)] = issue
        issues.save()
        return await ctx.send("Response added for Issue #{id}.".format(id=issue.id))

    @command(grant_level="explicit", aliases=['ic'])
    async def issueclose(self, ctx, id=None):
        """
        Syntax: `{pre}{command_name} <id>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Closes the specified issue once it has been resolved.

        __**Arguments**__
        `<id>` The ID number of the issue to close.

        __**Example Usage**__
        `{pre}{command_name} 69`
        """
        if id is None:
            return await ctx.send(f"You must specify the ID:\n{conf.prefix}issueclose <id>")
        if not id.isdigit():
            return await ctx.send("Invalid ID number: `{id}`.".format(id=id))
        try:
            issue = IssuesMaster.obtain(id=int(id))
        except KeyError:
            return await ctx.send("No issue with the ID `{id}` exists.".format(id=id))
        issues = IssuesMaster.obtain()
        if "#open" not in issue.status_tags:
            return await ctx.send("Issue #{id} is already closed.".format(id=id))
        issue.status_tags.remove("#open")
        issue.status_tags.append("#closed")
        issues.issues[str(issue.id)] = issue
        issues.save()
        return await ctx.send("Issue #{id} closed.".format(id=id))

    @command(grant_level="explicit", aliases=['iro'])
    async def issuereopen(self, ctx, id=None):
        """
        Syntax: `{pre}{command_name} <id>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Reopens the issue with the specified ID.

        __**Arguments**__
        `<id>` - The issue ID to reopen.

        __**Example Usage**__
        `{pre}{command_name} 69`
        """
        if id is None:
            return await ctx.send(f"You must specify the ID:\n{conf.prefix}issuereopen <id>")
        if not id.isdigit():
            return await ctx.send("Invalid ID number: `{id}`.".format(id=id))
        try:
            issue = IssuesMaster.obtain(id=int(id))
        except KeyError:
            return await ctx.send("No issue with the ID `{id}` exists.".format(id=id))
        issues = IssuesMaster.obtain()
        if "#closed" not in issue.status_tags:
            return await ctx.send("Issue #{id} is not closed, and therefore cannot be re-opened.".format(id=id))

        issue.status_tags.remove("#closed")
        issue.status_tags.append("#open")
        issues.issues[str(issue.id)] = issue
        issues.save()
        return await ctx.send("Issue #{id} reopened.".format(id=id))

    @command(grant_level="explicit", aliases=['it'])
    async def issuetag(self, ctx, command=None, status=None, id=None):
        """
        Syntax: `{pre}{command_name} <command> <#tag> <id>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Adds and removes issue tags to and from issues.
        Can be remembered with the mnemonic `add` `#thistag` to `This ID`.

        __**Arguments**__
        `<command>` - The operation to perform. Must be either `add` or `remove`.
        `<#tag>` - The tag to add or remove.
        `<id>` - The ID of the issue to perform the operation on.

        __**Example Usage**__
        `{pre}{command_name} add #critical 69`
        """
        if any([tag is None for tag in [command, status, id]]):
            return await ctx.send(f"One or more arguments were not provided. The syntax of the command is as follows:\n`{conf.prefix}issuetag <add|remove> <#tag> <issueid>`")
        id = int(id)
        edit_tags = []
        status = status.split(",")
        for s in status:
            s = s.replace("#", "") if s.startswith("#") else s
            if s not in conf.issues.validTags:
                return await ctx.send("`" + s + "` is not a valid status tag defined in the constants. Valid tags are:\n" + ", ".join(list(["`{tag}`".format(tag=tag) for tag in conf.issues.validTags])))
            edit_tags.append(s)

        try:
            issue = IssuesMaster.obtain(id=id)
            issues = IssuesMaster.obtain()
        except KeyError:
            return await ctx.send("No issue with the specified ID exists.")

        if command == "add":
            if any([tag in issue.status_tags for tag in edit_tags]):
                return await ctx.send("One or more of the specified tags are already attached to this issue.")
            for tag in edit_tags:
                issue.status_tags.append(tag)
            issues.issues[str(issue.id)] = issue
            issues.save()
            return await ctx.send("Tag(s) added to issue #" + str(id))
        if command == "remove":
            if any([tag not in issue.status_tags for tag in edit_tags]):
                return await ctx.send("One or more of the specified tags are not attached to this issue.")
            for tag in edit_tags:
                issue.status_tags.remove(tag)
            issues.issues[str(issue.id)] = issue
            issues.save()
            return await ctx.send("Tag(s) removed from issue #" + str(id))


def setup(bot):
    """Set up the issues cog."""
    bot.add_cog(Issues(bot))
