"""Module defines custom fields for the core config

    * Timezone - A zoneinfo timezone field
    * LogLevel - A log level field
    * DiscordUID - A unique Discord ID
    * TCPIPPort - A TCP/IP port number
    * ExistingPath - A POSIX path to a location on the system 
"""

import os
import zoneinfo
from marshmallow import fields, validate, ValidationError


class Timezone(fields.Str):
    def __init__(self, *args, **kwargs):
        kwargs['validate'] = validate.OneOf(zoneinfo.available_timezones())
        super().__init__(*args, **kwargs)


class LogLevel(fields.Str):
    LEVELS = [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL"
    ]

    def __init__(self, *args, **kwargs):
        kwargs['validate'] = validate.OneOf(LogLevel.LEVELS)
        super().__init__(*args, **kwargs)


class DiscordUID(fields.Int):
    def __init__(self, *args, **kwargs):
        kwargs['validate'] = validate.Range(min=100000000000000000, max=999999999999999999)
        super().__init__(*args, **kwargs)


class TCPIPPort(fields.Int):
    def __init__(self, *args, **kwargs):
        kwargs['validate'] = validate.Range(min=0, max=65535)
        super().__init__(*args, **kwargs)


class ExistingPath(fields.Str):
    def __init__(self, *args, **kwargs):
        self.create = kwargs.pop("create", False)
        kwargs['validate'] = self.validator
        super().__init__(*args, **kwargs)
    
    def validator(self, path):
        if self.allow_none is False or path is not None:
            if not os.path.exists(path):
                if self.create is True:
                    try:
                        os.makedirs(path)
                    except OSError as e:
                        raise ValidationError(f"The path '{path}' does not exist, and could not be created due to the following error: {e}")
                else:
                    raise ValidationError(f"The path '{path}' does not exist.")
        
                    