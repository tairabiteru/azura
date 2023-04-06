from ext.pagination import *
import orm.models as models
import orm.fields as fields

import enum
import hikari
import miru
import tortoise


class IssueStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class IssueResponse(models.HikariModel):
    author = fields.UserField()
    text = tortoise.fields.TextField()
    timestamp = tortoise.fields.DatetimeField(auto_now_add=True)

    def total_length(self):
        return len(self.stamp) + len(self.text)

    @property
    def stamp(self):
        return f"[{self.timestamp.strftime('%x')}][{self.author.username}]"


class IssueSelect(miru.Select):
    def __init__(self, issues, *args, **kwargs):
        self.issues = issues

        kwargs['options'] = []
        for i, issue in enumerate(self.issues):
            kwargs['options'].append(miru.SelectOption(f"{issue.id} - {issue.title}", value=issue.id))
        super().__init__(*args, **kwargs)

    async def callback(self, ctx):
        issue = await Issue.get(id=int(self.values[0]))
        menu = await issue.get_menu()
        await ctx.edit_response(menu.pages[0], components=menu.build())
        menu.start(ctx.message)
        await menu.wait()


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


class Issue(models.HikariModel):
    title = tortoise.fields.CharField(100)
    author = fields.UserField()
    description = tortoise.fields.TextField()
    status = tortoise.fields.CharEnumField(IssueStatus)
    timestamp = tortoise.fields.DatetimeField(auto_now_add=True)
    responses = tortoise.fields.ManyToManyField("models.IssueResponse")

    @classmethod
    async def open(cls, author, title, description="No description provided."):
        return await cls.create(title=title, author=author, description=description, status=IssueStatus.OPEN)

    async def close(self):
        self.status = IssueStatus.CLOSED
        await self.save()

    async def reopen(self):
        self.status = IssueStatus.OPEN
        await self.save()

    async def respond(self, author, response):
        response = await IssueResponse.create(author=author, text=response)
        await self.responses.add(response)
        await self.save()

    def _get_base_embed(self):
        embed = hikari.Embed(title=f"**Issue #{self.id} - {self.title}**")
        embed.description = self.description
        embed.add_field(name="Author", value=self.author.username, inline=True)
        embed.add_field(name="Status", value=self.status.value, inline=True)
        embed.add_field(name="Timestamp", value=self.timestamp.strftime("%x"), inline=True)
        return embed

    async def get_embeds(self):
        all_embeds = []
        embed = self._get_base_embed()

        responses = await self.responses
        if not responses:
            embed.add_field(name="**No Responses**", value="No one has responded to this issue yet.")
            all_embeds.append(embed)
            return all_embeds

        for response in responses:
            if response.total_length() + embed.total_length() >= 6000:
                all_embeds.append(embed)
                embed = self._get_base_embed()

            embed.add_field(name=f"{response.stamp}", value=response.text, inline=False)

        if embed not in all_embeds and embed.fields != self._get_base_embed().fields:
            all_embeds.append(embed)

        return all_embeds

    async def get_menu(self):
        pages = await self.get_embeds()
        return PaginatedView(pages, page=0)
