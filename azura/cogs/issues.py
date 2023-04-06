"""
Define the issues plugin.

The issues plugin is used as a built in issue tracker to keep track of issues with the bot's code.
"""

from core.conf import conf

import orm.models as models

import keikou


issues = keikou.Plugin("issues")
issues.description = f"Plugin containing commands related to {conf.parent.name}'s built in issue tracking system."


@issues.command()
@keikou.command("issue", f"Commands related to {conf.parent.name}'s built in issue tracking system.")
@keikou.implements(keikou.SlashCommandGroup)
async def issue(ctx):
    pass


@issue.child()
@keikou.option("description", "The description of the issue to open.", default="No description provided.")
@keikou.option("title", "The title of the issue you want to open. Maximum of 100 characters.")
@keikou.command("open", f"Open an issue in {conf.parent.name}'s issue tracker.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_open(ctx):
    description = ctx.options.description if ctx.options.description is not None else "No description provided."
    issue = await models.Issue.open(ctx.author, ctx.options.title, description=description)
    menu = await issue.get_menu()
    resp = await ctx.respond(f"Issue opened with ID #{issue.id}:", embed=menu.pages[0], components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()


@issue.child()
@keikou.option("id", "The ID of the issue to close.", type=int)
@keikou.command("close", "Close an issue.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_close(ctx):
    issue = await models.Issue.get(id=ctx.options.id)
    await issue.close()
    menu = await issue.get_menu()
    resp = await ctx.respond(f"Issue #{issue.id} closed:", embed=menu.pages[-1], components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()


@issue.child()
@keikou.option("response", "The response to the issue.")
@keikou.option("id", "The ID of the issue to respond to and close.", type=int)
@keikou.command("respondclose", "Respond to an issue, then close it afterwards.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_respondclose(ctx):
    issue = await models.Issue.get(id=ctx.options.id)
    await issue.respond(ctx.author, ctx.options.response)
    await issue.close()
    menu = await issue.get_menu()
    resp = await ctx.respond(f"Responded to issue #{issue.id}. It has been closed:", embed=menu.pages[-1], components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()


@issue.child()
@keikou.option("response", "The response to the issue.")
@keikou.option("id", "The ID of the issue to respond to.", type=int)
@keikou.command("respond", "Respond to an issue.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_respond(ctx):
    issue = await models.Issue.get(id=ctx.options.id)
    await issue.respond(ctx.author, ctx.options.response)
    menu = await issue.get_menu()
    resp = await ctx.respond(f"Responded to issue #{issue.id}:", embed=menu.pages[-1], components=menu.build())
    menu.start((await resp.message()))
    await menu.wait()


@issue.child()
@keikou.option("id", "The ID of the issue to list. If not specified, all open issues will be shown.", type=int, default=None)
@keikou.command("list", "List issues, or view a specific issue.")
@keikou.implements(keikou.SlashSubCommand)
async def issue_list(ctx):
    if ctx.options.id is not None:
        issue = await models.Issue.get(id=ctx.options.id)
        menu = await issue.get_menu()
        resp = await ctx.respond(menu.pages[0], components=menu.build())
        menu.start((await resp.message()))
        await menu.wait()
    else:
        issues = await models.Issue.all().filter(status=models.IssueStatus.OPEN)
        if not issues:
            return await ctx.respond("There are no open issues at the moment.")

        menu = models.MultiIssueMenu(issues, title="All Open Issues", description="All issues with status OPEN.")
        resp = await ctx.respond(menu.pages[0], components=menu.build())
        menu.start((await resp.message()))
        await menu.wait()


def load(bot):
    bot.add_plugin(issues)


def unload(bot):
    bot.remove_plugin(issues)
