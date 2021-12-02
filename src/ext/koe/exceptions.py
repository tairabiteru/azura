class KoeException(Exception):
    """Base exception for all Koe errors."""
    pass


class AlreadyConnected(KoeException):
    """Raised when a connection attempt occurs when one already exists."""

    def __init__(self, gid, vid):
        self.gid = gid
        self.vid = vid
        self.message = f"Connection attempt in guild #{self.gid} cannot proceed due to existing connection to channel #{self.vid}."
        super().__init__(self.message)


class NoVoiceChannel(KoeException):
    """Raised when a connection attempt is made from CTX without a user voice connection."""

    def __init__(self, gid, uid):
        self.gid = gid
        self.uid = uid
        self.message = f"Connection attempt in guild #{self.gid} failed for user #{self.uid}. No voice connection present."
        super().__init__(self.message)


class NoExistingSession(KoeException):
    """Raised when an attempt is made to retreive an existing session which does not exist."""

    def __init__(self, vid):
        self.vid = vid
        self.message = f"No session exists for voice channel #{self.vid}."
        super().__init__(self.message)


class NoAvailableEndpoint(KoeException):
    """Raised when a request is made for an endpoint which isn't available."""

    def __init__(self, gid):
        self.gid = gid
        self.message = f"No endpoints are currently available for guild #{self.gid}."
        super().__init__(self.message)


class BadResponse(KoeException):
    """Raised when a request is made expecting a response, but that response is invalid."""
    pass


class TrackNotFound(KoeException):
    """Raised when a requested track could not be found."""
    pass
