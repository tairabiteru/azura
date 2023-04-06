"""Extended command functions which assist in dealing with slash command context."""
from ext.utils import localnow

import asyncio
import hikari
import miru


def as_embed(url, **kwargs):
    embed = hikari.embeds.Embed(**kwargs)
    embed.set_image(url)
    return embed


def getHideOrNone(ctx):
    """
    Obtain the option flags for a slash command with an ephemeral option.

    If the command has an ephemeral option, checks for it and returns the
    appropriate hikari message flags.
    """
    if ctx.options.hide or ctx.options.hide is None:
        return hikari.MessageFlag.EPHEMERAL
    else:
        return hikari.MessageFlag.NONE


def getMemberOrAuthor(ctx):
    """Return the specified member from options, if specified, else author."""
    if ctx.options.member is None:
        return ctx.member
    else:
        return ctx.bot.cache.get_member(ctx.guild_id, ctx.resolved.users[int(ctx.options.member)])


async def create_timeout_message(bot, cid, message, timeout):
    async def delete_after(message, timeout):
        await asyncio.sleep(timeout)
        await message.delete()

    message = await bot.rest.create_message(cid, message)
    loop = hikari.internal.aio.get_or_make_loop()
    loop.create_task(delete_after(message, timeout))


async def respond_with_timeout(ctx, message, timeout):
    async def delete_after(resp, timeout):
        await asyncio.sleep(timeout)
        await resp.delete()

    resp = await ctx.respond(message)
    loop = hikari.internal.aio.get_or_make_loop()
    loop.create_task(delete_after(resp, timeout))


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


class ValidationSelect(miru.Select):
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

    async def on_timeout(self):
        self.result = False
        self.reason = "Operation timed out."


async def sendWebhookMessage(ctx, name, url, message):
    webhook = await ctx.bot.rest.create_webhook(
        ctx.channel_id,
        name,
        avatar=url,
    )
    await ctx.bot.rest.execute_webhook(webhook, webhook.token, content=message)
    await ctx.bot.rest.delete_webhook(webhook)


class DelayedResponse:
    def __init__(self, ctx, initial_response, timeout=10):
        self.ctx = ctx
        self.initial_response = initial_response
        self.contents = initial_response
        self.timeout = timeout
        self.update_task = None
        self.start_time = None

    async def update(self):
        while (localnow() - self.start_time).total_seconds() < self.timeout:
            self.contents += "."
            await self.ctx.edit_last_response(self.contents)
            await asyncio.sleep(1)
        await self.ctx.edit_last_response("The operation failed to complete within the timeout period.")
        raise asyncio.TimeoutError

    async def complete(self, *args, **kwargs):
        self.update_task.cancel()
        await self.ctx.edit_last_response(*args, **kwargs)

    async def __aenter__(self):
        await self.ctx.respond(self.initial_response)

        loop = hikari.internal.aio.get_or_make_loop()
        self.update_task = loop.create_task(self.update())
        self.start_time = localnow()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass
