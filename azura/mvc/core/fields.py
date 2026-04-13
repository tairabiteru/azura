from django.db import models
import zoneinfo


class TimezoneField(models.CharField):
    CHOICES = list([(tz, tz) for tz in sorted(zoneinfo.available_timezones())])

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 64
        kwargs['choices'] = TimezoneField.CHOICES
        kwargs['default'] = 'UTC'
        super().__init__(*args, **kwargs)


class LocationField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 128
        super().__init__(*args, **kwargs)
