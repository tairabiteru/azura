"""Module contains exceptions used by the player."""

from discord.ext import commands


class AlreadyConnectedToChannel(commands.CommandError):
    """Raise when the bot cannot connect due to already being connected."""

    pass


class NoVoiceChannel(commands.CommandError):
    """Raise when there is no voice channel that can be connected to."""

    pass


class QueueIsEmpty(commands.CommandError):
    """Raise when queue is accessed while empty."""

    pass


class EndOfQueue(commands.CommandError):
    """Raise when queue's position is higher than length."""

    pass


class NoTracksFound(commands.CommandError):
    """Raise when wavelink fails to find a track."""

    pass
