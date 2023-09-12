from django.db import models
from .base import DiscordBaseModel
from ...core.fields import TimezoneField
from ....ext.utils import utcnow
import zoneinfo


class Locale(DiscordBaseModel):
    DATE_FORMATS = [
        ('%-m/%-d/%Y', 'mm/dd/yyyy'),
        ('%-d/%-m/%Y', 'dd/mm/yyyy'),
        ('%Y/%m/%d', 'yyyy/mm/dd'),
        ('%-m-%-d-%Y', 'mm-dd-yyyy'),
        ('%-d-%-m-%Y', 'dd-mm-yyyy'),
        ('%Y-%m-%d', 'yyyy-mm-dd')
    ]

    TIME_FORMATS = [
        ('%-I:%M:%S %p %Z', '12-hr HH:MM:SS Z'),
        ('%-H:%M:%S %Z', '24-hr HH:MM:SS Z'),
        ('%-I:%M %Z', '12-hr HH:MM Z'),
        ('%-H:%M %Z', '24-hr HH:MM Z')
    ]

    date_format = models.CharField(max_length=32, choices=DATE_FORMATS, default="%-m/%-d/%Y", help_text="Your preferred date format.")
    time_format = models.CharField(max_length=32, choices=TIME_FORMATS, default="%-I:%M:%S %p %Z", help_text="Your preferred time format.")
    timezone = TimezoneField(help_text="Your timezone.")

    @property
    def datetime_format(self):
        return f"{self.date_format} {self.time_format}"
    
    def aslocaltime(self, time):
        return time.astimezone(zoneinfo.ZoneInfo(self.timezone))
    
    def localnow(self):
        return self.aslocaltime(utcnow())
    
    def __str__(self):
        try:
            self.user.attach_bot(self._bot)
            return f"Locale Settings for {self.user.obj.username}"
        except (ValueError, AttributeError):
            return f"Locale Settings for UID ({self.user.id})"