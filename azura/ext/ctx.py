"""Helper module containing functions and classes related to command context

The items defined in here are all fairly disconnected, but their common
thread is that they are all in some way related to the handling of command
execution and response.

    * as_embed - Function that turns an image URL into a hikari.Embed object
    * ReinitEmbed - Specific embed sent when Farore reinitializes
    * ValidationSelect - miru.TextSelect menu which is used with ValidationMenu
    * ValidationMenu - miru.View which is used to validate important or destructive actions
    * DelayedResponse - Async context manager used to defer the response to commands with long execution times
    * PaginatedView - miru.View used to paginate items in an application command response
    * send_webhook_message - Function used to send a webhook message impersonating other users
    * ChainedMessage - Class implementing 'chained message' behavior abstracting the continued update of a response
    * contains_mention - Function returning boolean if a string contains a Discord mention
    * contains_mention_of - Function returning boolean if a string contains a Discord mention of the passed item
    * ImageTable - Class for creating and displaying tables in Discord as an image
    * TextTable - Class for doing the above, but with text instead of images
"""

import asyncio
import hikari
import io
import miru
import re
import plotly.figure_factory as figure_factory


def as_embed(url, **kwargs):
    embed = hikari.Embed(**kwargs)
    embed.set_image(url)
    return embed


class ReinitEmbed(hikari.Embed):
    def __init__(self, type, details):
        if type == "pre":
            super().__init__(title="**REINITIALIZATION CALL**")
            self.set_thumbnail("https://media0.giphy.com/media/3o7bu3XilJ5BOiSGic/giphy.gif")
        if type == "post":
            super().__init__(title="**Reinitialization Complete**")
            self.set_thumbnail("https://www.clipartmax.com/png/middle/301-3011315_icon-check-green-tick-transparent-background.png")
        self.description = details


class ValidationSelect(miru.TextSelect):
    def __init__(self, view, *args, **kwargs):
        kwargs['options'] = [
            miru.SelectOption(view.yes_msg, value="True"),
            miru.SelectOption(view.no_msg, value="False")
        ]
        super().__init__(*args, **kwargs)

    async def callback(self, ctx):
        self.view.result = self.values[0] == "True"
        self.view.reason = "Operation cancelled." if not self.view.result else "Operation validated."
        self.view.stop()


class ValidationMenu(miru.View):
    def __init__(self, *args, **kwargs):
        self.yes_msg = kwargs.pop("yes_msg", "Yes")
        self.no_msg = kwargs.pop("no_msg", "No")

        self.result: bool = None
        self.reason: str = None

        super().__init__(*args, **kwargs)
        self.add_item(ValidationSelect(self))
    
    async def view_check(self, ctx):
        return ctx.author.id == ctx.interaction.member.id

    async def on_timeout(self):
        self.result = False
        self.reason = "Operation timed out."


class DelayedResponse:
    def __init__(self, ctx, initial_response, timeout=10):
        self.ctx = ctx
        self.initial_response = initial_response
        self.contents = initial_response
        self.timeout = timeout
        self.update_task = None
        self.start_time = None

    async def update(self):
        while (self.ctx.bot.localnow() - self.start_time).total_seconds() < self.timeout:
            self.contents += "."
            await self.ctx.edit_last_response(self.contents)
            await asyncio.sleep(1)
        await self.ctx.edit_last_response("The operation failed to complete within the timeout period.")
        raise asyncio.TimeoutError

    async def complete(self, *args, **kwargs):
        self.update_task.cancel()
        return await self.ctx.edit_last_response(*args, **kwargs)

    async def __aenter__(self):
        await self.ctx.respond(self.initial_response)

        loop = hikari.internal.aio.get_or_make_loop()
        self.update_task = loop.create_task(self.update())
        self.start_time = self.ctx.bot.localnow()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class PageRevButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⬅️")

    async def callback(self, ctx):
        await self.view.change_page(ctx, self.view.page-1)


class PageAdvButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="➡️")

    async def callback(self, ctx):
        await self.view.change_page(ctx, self.view.page+1)


class PageStartButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⏪")

    async def callback(self, ctx):
        await self.view.change_page(ctx, 0)


class PageEndButton(miru.Button):
    def __init__(self):
        super().__init__(style=hikari.ButtonStyle.PRIMARY, label="⏩")

    async def callback(self, ctx):
        await self.view.change_page(ctx, len(self.view.pages)-1)


class PaginatedView(miru.View):
    def __init__(self, pages, *args, page=0, **kwargs):
        self.pages = pages
        self.page = page

        super().__init__(*args, **kwargs)
        self.update_buttons()
    
    async def view_check(self, ctx):
        return ctx.author.id == ctx.interaction.member.id

    async def change_page(self, ctx, page):
        self.page = page
        self.update_buttons()
        await ctx.edit_response(self.current, components=self.build())

    @property
    def current(self):
        return self.pages[self.page]

    def update_buttons(self):
        self.clear_items()
        if self.page != 0:
            self.add_item(PageStartButton())
            self.add_item(PageRevButton())
        if self.page != len(self.pages)-1:
            self.add_item(PageAdvButton())
            self.add_item(PageEndButton())

    def build(self):
        try:
            return super().build()
        except ValueError:
            return []


async def send_webhook_message(ctx, name, url, message):
    webhook = await ctx.bot.rest.create_webhook(ctx.channel_id, name, avatar=url)
    await ctx.bot.rest.execute_webhook(webhook, webhook.token, content=message)
    await ctx.bot.rest.delete_webhook(webhook)


class ChainedMessage:
    """
    Class that helps with situations where you want to chain messages together.

    This is good in scenarios where you're repeatedly editing a response.
    This class can operate both with interaction contexts, and channel IDs. If
    the channel ID is used, the bot must also be specified.
    """
    def __init__(self, ctx=None, cid=None, bot=None, header="", wrapper="", response_exists=False, show_wrappers_without_content=False):
        if ctx is None and cid is None:
            raise ValueError("One of 'ctx' or 'cid' kwargs must be set.")
        if ctx is None and cid is not None and bot is None:
            raise ValueError("If 'ctx' is not provided and 'cid' is provided, the 'bot' kwarg must be set.")

        self.ctx = ctx
        self.cid = cid

        if bot is None:
            self.bot = ctx.bot
        else:
            self.bot = bot

        self._header = header
        self._wrapper = wrapper
        self._content = ""
        self._responseExists = response_exists
        self._showWrappersWithoutContent = show_wrappers_without_content
        self._msg = None

    @property
    def content(self):
        if self._content == "" and self._showWrappersWithoutContent is False:
            return f"{self._header}"
        return f"{self._header}{self._wrapper}{self._content}{self._wrapper}"

    async def update(self):
        if self.ctx is not None and self.cid is None:
            if not self._responseExists:
                await self.ctx.respond(self.content)
                self._responseExists = True
            else:
                await self.ctx.edit_last_response(self.content)
        else:
            if not self._responseExists:
                self._msg = await self.bot.rest.create_message(self.cid, self.content)
                self._responseExists = True
            else:
                await self._msg.edit(self.content)

    async def setHeader(self, header):
        self._header = header
        await self.update()

    async def setWrapper(self, wrapper):
        self._wrapper = wrapper
        await self.update()

    async def append(self, string):
        self._content += string
        await self.update()


def contains_mention(text):
    matches = re.findall("<@![0-9]{18}>", text)
    matches += re.findall("<@[0-9]{18}>", text)
    return True if matches else False


def contains_mention_of(text, user):
    return user.mention.replace("!", "") in text


class ImageTable:
    def __init__(self, rows=[]):
        self.rows = rows
        self.plot = figure_factory.create_table(self.rows)
        self.io = io.BytesIO()
        self.plot.write_image(self.io, width=800, height=40 * len(rows))
        self.file = hikari.files.Bytes(self.io.getvalue(), "imagetable.png")


class TextTable:
    def __init__(self, rows=[], padding=1):
        self.rows = rows
        self.padding = padding

    @property
    def columns(self):
        return list(zip(*self.rows))

    @property
    def headers(self):
        return self.rows[0]

    def get_colw(self, col):
        lens = []
        for element in col:
            lens.append(len(str(element)))
        return max(lens)

    @property
    def rendered(self):
        table_by_column = []
        for column in self.columns:
            colw = self.get_colw(column)
            new_column = []
            for item in column:
                padding_needed = colw - len(str(item))
                item = str(item) + " " * padding_needed
                new_column.append(item)
            table_by_column.append(new_column)
        rows = list(zip(*table_by_column))
        table = ""
        for row in rows:
            padding = " " * self.padding
            line = "|"
            for item in row:
                line += padding + item + padding + "|"
            table += line + "\n"
        return table


async def create_timeout_message(bot, cid, message=None, embed=None, components=[], timeout=5):
    async def delete_after(message, timeout):
        await asyncio.sleep(timeout)
        await message.delete()

    message = await bot.rest.create_message(cid, content=message, embed=embed, components=components)
    loop = hikari.internal.aio.get_or_make_loop()
    loop.create_task(delete_after(message, timeout))


async def respond_with_timeout(ctx, message, timeout):
    async def delete_after(resp, timeout):
        await asyncio.sleep(timeout)
        await resp.delete()

    resp = await ctx.respond(message)
    loop = hikari.internal.aio.get_or_make_loop()
    loop.create_task(delete_after(resp, timeout))