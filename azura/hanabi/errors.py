class HanabiError(Exception):
    """Generic error created by hanabi."""
    pass


class NoSessionExists(HanabiError):
    """
    Error occurs when a session is expected to exist
    but doesn't.
    """
    pass


class SessionAlreadyExists(HanabiError):
    """
    Error occurs when a session is to be created,
    but a session with the same VID already exists.
    """
    pass


class NotAvailable(HanabiError):
    """
    Error occurs either when no bots are available
    to connect, or when a specific bot is requested,
    but that bot is not available.
    """
    pass


class InvalidName(HanabiError):
    """
    Error occurs when a specific bot is requested,
    but the name given can't be matched to any bot.
    """
    pass


class InvalidSetting(HanabiError):
    """
    Error occurs when an invalid setting is passed,
    for example, exceeding the maximum volume.
    """
    pass


class QueueError(HanabiError):
    """Base error for the queue."""
    pass


class InvalidPosition(QueueError):
    """
    Error occurs when an attempt is made to
    place the queue in an invalid position, for
    example, if the queue is 3 items long, and
    someone tries to advance forward by 5.
    """
    pass
