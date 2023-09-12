from ..discord.models import DiscordBaseModel, User
from ...ext.ctx import PaginatedView, PageStartButton, PageRevButton, PageAdvButton, PageEndButton
from django.db import models


import copy
import hikari
import miru


class IssueSelect(miru.TextSelect):
    def __init__(self, issues, *args, **kwargs):
        self.issues = issues

        kwargs['options'] = []
        for i, issue in enumerate(self.issues):
            kwargs['options'].append(miru.SelectOption(f"{issue.id} - {issue.title}", value=issue.id))
        super().__init__(*args, **kwargs)

    async def callback(self, ctx):
        issue = await Issue.objects.select_related("author").aget(id=int(self.values[0]))
        menu = await issue.get_menu(ctx)
        await ctx.edit_response(menu.pages[0], components=menu.build())
        await menu.start(ctx.message)


class MultiIssueMenu(PaginatedView):
    def __init__(self, issues, title="Issues", description="All issues.", *args, **kwargs):
        self.issues = issues

        all_pages = []
        current = hikari.Embed(title=title)
        current.description = description

        for issue in self.issues:
            if len(current.fields) >= 10:
                all_pages.append(current)
                current = hikari.Embed(title=title)
                current.description = description
            current.add_field(name=f"{issue.id} - {issue.title}", value=f"Opened on {issue.timestamp.strftime('%c')}")

        if current not in all_pages and len(current.fields) != 0:
            all_pages.append(current)

        super().__init__(all_pages, page=0, *args, **kwargs)

    def update_buttons(self):
        self.clear_items()
        self.add_item(IssueSelect(self.issues[10*self.page:(10*self.page)+10]))

        if self.page != 0:
            self.add_item(PageStartButton())
            self.add_item(PageRevButton())
        if self.page != len(self.pages)-1:
            self.add_item(PageAdvButton())
            self.add_item(PageEndButton())



class Response(DiscordBaseModel):
    author = models.ForeignKey("discord.User", null=True, on_delete=models.SET_NULL, help_text="The person who wrote this response.")
    text = models.TextField(help_text="The text of the response.")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="The time when this response was given.")

    async def get_timestamp(self, locale, bot):
        self.author.attach_bot(bot)
        await self.author.aresolve_all()
        return f"[{self.timestamp.strftime(locale.date_format)}][{self.author.obj.username}]"
    
    def __str__(self):
        return self.text


class Issue(DiscordBaseModel):
    STATUSES = [
        ('OPEN', 'OPEN'),
        ('CLOSED', 'CLOSED')
    ]

    author = models.ForeignKey("discord.User", null=True, on_delete=models.SET_NULL, help_text="The person who opened this issue.")
    title = models.CharField(max_length=100, help_text="The title of this issue.")
    description = models.TextField(null=True, blank=True, help_text="The description of this issue.")
    status = models.CharField(max_length=10, choices=STATUSES, default="OPEN", help_text="The status of this issue.")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="The time when this issue was first opened.")
    responses = models.ManyToManyField(Response)

    @classmethod
    async def open(cls, author, title, description="No description provided."):
        o = cls(author=author, title=title, description=description)
        await o.asave()
        return o
    
    async def close(self):
        self.status = 'CLOSED'
        await self.asave()
        return self
    
    async def reopen(self):
        self.status = 'OPEN'
        await self.asave()
        return self
    
    async def respond(self, author, response):
        response = Response(author=author, text=response)
        await response.asave()
        await self.responses.aadd(response)
        await self.asave()
        return self
    
    async def _get_base_embed(self, locale, ctx):
        self.author.attach_bot(ctx.bot)
        await self.author.aresolve_all()

        embed = hikari.Embed(title=f"**Issue #{self.id} - {self.title}**")
        embed.description = self.description
        embed.add_field(name="Author", value=self.author.obj.username, inline=True)
        embed.add_field(name="Status", value=self.status, inline=True)
        embed.add_field(name="Timestamp", value=self.timestamp.strftime(locale.date_format), inline=True)
        return embed

    async def get_embeds(self, ctx):
        all_embeds = []
        user, _ = await User.objects.aget_or_create(id=ctx.author.id)
        locale = (await User.objects.select_related("locale_settings").aget(id=user.id)).locale_settings

        embed = await self._get_base_embed(locale, ctx)
        base = copy.deepcopy(embed)

        if (await self.responses.acount()) == 0:
            embed.add_field(name="**No Responses**", value="No one has responded to this issue yet.")
            all_embeds.append(embed)
            return all_embeds

        async for response in self.responses.all():
            response = await Response.objects.select_related("author").aget(id=response.id)
            timestamp = await response.get_timestamp(locale, ctx.bot)
            if (len(timestamp) + len(response.text)) + embed.total_length() >= 6000:
                all_embeds.append(embed)
                embed = copy.deepcopy(base)

            embed.add_field(name=f"{timestamp}", value=response.text, inline=False)

        if embed not in all_embeds and embed.fields != base.fields:
            all_embeds.append(embed)

        return all_embeds

    async def get_menu(self, ctx):
        pages = await self.get_embeds(ctx)
        return PaginatedView(pages, page=0)
