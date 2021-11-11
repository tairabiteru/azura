"""Extended command functions which assist in dealing with slash command context."""

import hikari
import random


def as_embed(url, **kwargs):
    embed = hikari.embeds.Embed(**kwargs)
    embed.set_image(url)
    return embed


def getEphemeralOrNone(ctx):
    """
    Obtain the option flags for a slash command with an ephemeral option.

    If the command has an ephemeral option, checks for it and returns the
    appropriate hikari message flags.
    """
    if ctx.options.ephemeral or ctx.options.ephemeral is None:
        return hikari.messages.MessageFlag.EPHEMERAL
    else:
        return None


def getMemberOrAuthor(ctx):
    """Return the specified member from options, if specified, else author."""
    if ctx.options.member is None:
        return ctx.member
    else:
        return ctx.resolved.users[int(ctx.options.member)]


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
                await self.ctx.edit_response(self.content)
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


class ValidationError(Exception):
    """Raised when a validation operation is not successful."""
    pass


class Validation:
    SYMBOLS = ["⭕", "🔰", "❌", "💠", "🔱", "❓", "❗", "🎵"]

    def __init__(self, ctx, message, timeout=20):
        self.ctx = ctx
        self.message = message
        self.timeout = timeout

    async def __aenter__(self):
        row = self.ctx.bot.rest.build_action_row()
        valid_symbol = random.randint(0, 2)
        for i in range(0, 3):
            symbol = Validation.SYMBOLS.pop(random.randint(0, len(Validation.SYMBOLS)-1))
            if i == valid_symbol:
                valid_symbol = symbol
            row.add_button(
                hikari.ButtonStyle.SECONDARY,
                symbol
            ).set_label(symbol).add_to_container()
        await self.ctx.respond(f"{self.message}\nIf you're sure about this, please press {valid_symbol} in the next {self.timeout} seconds.", components=[row])
        msg = await self.ctx.interaction.fetch_initial_response()

        async with self.ctx.bot.stream(hikari.InteractionCreateEvent, self.timeout).filter(
            lambda event: (
                isinstance(event.interaction, hikari.ComponentInteraction)
                and event.interaction.user.id == self.ctx.author.id
                and event.interaction.message.id == msg.id
            )
        ) as stream:
            async for event in stream:
                if event.interaction.custom_id != valid_symbol:
                    raise ValidationError("Incorrect symbol selected, operation cancelled.")
                return

        raise ValidationError("Timeout has expired, operation cancelled.")

    async def __aexit__(self, *args):
        pass


async def sendWebhookMessage(ctx, name, url, message):
    webhook = await ctx.bot.rest.create_webhook(
        ctx.channel_id,
        name,
        avatar=url,
    )
    await ctx.bot.rest.execute_webhook(webhook, webhook.token, content=message)
    await ctx.bot.rest.delete_webhook(webhook)
