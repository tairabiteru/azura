class KoeError(Exception):
    pass


class NotConnectedToVoice(KoeError):
    pass


class NoExistingSession(KoeError):
    pass


class ExistingSession(KoeError):
    pass


class SessionBusy(KoeError):
    pass


class AllSessionsBusy(KoeError):
    pass


class InvalidResponse(KoeError):
    pass


class NoTracksFound(KoeError):
    pass


class QueueError(KoeError):
    pass


class InvalidPosition(QueueError):
    pass
