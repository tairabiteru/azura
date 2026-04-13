import hikari


class KoeException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
    
    
class NXSession(KoeException):
    def __init__(self, vid: hikari.Snowflake, operation: str | None=None):
        if operation is None:
            super().__init__(f"Session with Voice ID `{vid}` does not exist.")
        else:
            super().__init__(f"During {operation}, session with Voice ID `{vid}` does not exist.")


class EXSession(KoeException):
    def __init__(self, vid: hikari.Snowflake, operation: str | None=None):
        if operation is None:
            super().__init__(f"Session with Voice ID `{vid}` already exists.")
        else:
            super().__init__(f"During {operation}, session with Voice ID `{vid}` does already exists.")


class InvalidState(KoeException):
    def __init__(self, vid: hikari.Snowflake, operation: str | None=None):
        if operation is None:
            super().__init__(f"Voice connection for voice channel `{vid}` could not be retrieved.")
        else:
            super().__init__(f"During {operation}, voice connection for voice channel `{vid}` could not be retrieved.")