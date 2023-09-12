import azura.keikou as keikou

from ..core.conf.loader import conf
from ..mvc.discord.models import User
from ..mvc.issues.models import Issue, MultiIssueMenu

issues = keikou.Plugin("issues")
issues.description = f"Plugin contaianing commands related to {conf.name}'s built-in issue tracking system."


@issues.command()
@keikou.command("issue", f"Commands related to {conf.name}'s built-in issue tracking system.")
@keikou.implements(keikou.SlashCommandGroup)
async def issue(ctx):
    pass


@issue.child()
@keikou.option("description", "The description of the issue to open.", default="No description provided.")
@keikou.option("title", "The title of the issue you want to open. Maximum of 100 characters.")
@keikou.command("open", f"Open an issue in {conf.name}'s issue tracker.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_open(ctx):
    if len(ctx.options.title) > 100:
        return await ctx.respond(f"The title is {len(ctx.options.title)} characters long, which is too long. It must be 100 characters or fewer.")

    author, _ = await User.objects.aget_or_create(id=ctx.author.id)
    issue = Issue(author=author, title=ctx.options.title, description=ctx.options.description)
    await issue.asave()
    menu = await issue.get_menu(ctx)
    resp = await ctx.respond(f"Issue opened with ID #{issue.id}:", embed=menu.pages[0], components=menu.build())
    await menu.start((await resp.message()))


@issue.child()
@keikou.option("id", "The ID of the issue to close.", type=int)
@keikou.command("close", "Close an issue.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_close(ctx):
    try:
        issue = await Issue.objects.select_related("author").aget(id=ctx.options.id)
        if issue.status == "CLOSED":
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} is already closed:", embed=menu.pages[-1], components=menu.build())      
        else:
            await issue.close()
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} closed:", embed=menu.pages[-1], components=menu.build())
        await menu.start((await resp.message()))
    except Issue.DoesNotExist:
        return await ctx.respond(f"An issue with the ID `{ctx.options.id}` does not exist.")


@issue.child()
@keikou.option("id", "The ID of the issue to reopen.", type=int)
@keikou.command("reopen", "Reopen an issue.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_reopen(ctx):
    try:
        issue = await Issue.objects.select_related("author").aget(id=ctx.options.id)
        if issue.status == "OPEN":
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} is already open:", embed=menu.pages[-1], components=menu.build())      
        else:
            await issue.reopen()
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} reopened:", embed=menu.pages[-1], components=menu.build())
        await menu.start((await resp.message()))
    except Issue.DoesNotExist:
        return await ctx.respond(f"An issue with the ID `{ctx.options.id}` does not exist.")


@issue.child()
@keikou.option("response", "The response to the issue.")
@keikou.option("id", "The ID of the issue to respond to and close.", type=int)
@keikou.command("respondclose", "Respond to an issue, then close it afterwards.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_respondclose(ctx):
    try:
        issue = await Issue.objects.select_related("author").aget(id=ctx.options.id)
        if issue.status == "CLOSED":
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} is already closed:", embed=menu.pages[-1], components=menu.build())      
        else:
            user, _ = await User.objects.aget_or_create(id=ctx.author.id)
            await issue.respond(user, ctx.options.response)
            await issue.close()
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Responded to issue #{issue.id}. It has been closed:", embed=menu.pages[-1], components=menu.build())
        await menu.start((await resp.message()))
    except Issue.DoesNotExist:
        return await ctx.respond(f"An issue with the ID `{ctx.options.id}` does not exist.")


@issue.child()
@keikou.option("response", "The response to the issue.")
@keikou.option("id", "The ID of the issue to respond to.", type=int)
@keikou.command("respond", "Respond to an issue.", grant_level=keikou.EXPLICIT)
@keikou.implements(keikou.SlashSubCommand)
async def issue_respond(ctx):
    try:
        issue = await Issue.objects.select_related("author").aget(id=ctx.options.id)
        if issue.status == "CLOSED":
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Issue #{issue.id} is closed, and cannot be responded to:", embed=menu.pages[-1], components=menu.build())      
        else:
            user, _ = await User.objects.aget_or_create(id=ctx.author.id)
            await issue.respond(user, ctx.options.response)
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(f"Responded to issue #{issue.id}:", embed=menu.pages[-1], components=menu.build())
        await menu.start((await resp.message()))
    except Issue.DoesNotExist:
        return await ctx.respond(f"An issue with the ID `{ctx.options.id}` does not exist.")


@issue.child()
@keikou.option("id", "The ID of the issue to list. If not specified, all open issues will be shown.", type=int, default=None)
@keikou.command("list", "List issues, or view a specific issue.")
@keikou.implements(keikou.SlashSubCommand)
async def issue_list(ctx):
    if ctx.options.id is not None:
        try:
            issue = await Issue.objects.select_related("author").aget(id=ctx.options.id)
            menu = await issue.get_menu(ctx)
            resp = await ctx.respond(menu.pages[0], components=menu.build())
            await menu.start((await resp.message()))
        except Issue.DoesNotExist:
            return await ctx.respond(f"An issue with the ID `{ctx.options.id}` does not exist.")
    else:
        issues = Issue.objects.select_related("author").filter(status="OPEN")
        temp = []
        async for issue in issues:
            temp.append(issue)
        issues = sorted(temp, key=lambda i: i.timestamp)

        if not issues:
            return await ctx.respond("There are no open issues at the moment.")

        menu = MultiIssueMenu(issues, title="All Open Issues", description="All issues with status OPEN.")
        resp = await ctx.respond(menu.pages[0], components=menu.build())
        await menu.start((await resp.message()))


def load(bot):
    bot.add_plugin(issues)


def unload(bot):
    bot.remove_plugin(issues)