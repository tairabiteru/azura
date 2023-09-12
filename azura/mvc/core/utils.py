"""Module containing various utilities for the MVC

Similar to ext.utils, this file contains utilities specific to the Model-
View Controller.

    * TIMEZONE_CHOICES - shorthand constant listing all available zoneinfo timezones
    * template - Decorator taking a template name as an argument, and automatically returning a rendered request
"""

import zoneinfo
from django.shortcuts import render


TIMEZONE_CHOICES = list([(tz, tz) for tz in zoneinfo.available_timezones()])


def template(template):
    def inner(func):
        async def inner_inner(request):
            ctx = await func(request)
            return render(request, template, ctx)
        return inner_inner
    return inner