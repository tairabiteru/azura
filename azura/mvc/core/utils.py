"""Module containing various utilities for the MVC

Similar to ext.utils, this file contains utilities specific to the Model-
View Controller.

    * TIMEZONE_CHOICES - shorthand constant listing all available zoneinfo timezones
    * template - Decorator taking a template name as an argument, and automatically returning a rendered request
"""

import zoneinfo
from django.shortcuts import render
from django.db.transaction import Atomic
from asgiref.sync import sync_to_async
import inspect


TIMEZONE_CHOICES = list([(tz, tz) for tz in zoneinfo.available_timezones()])


def template(template):
    def inner(func):
        if inspect.iscoroutinefunction(func):
            async def inner_inner(request, *args, **kwargs):
                ctx = await func(request, *args, **kwargs)
                return render(request, template, ctx)
            return inner_inner
        else:
            def inner_inner(request, *args, **kwargs):
                ctx = func(request, *args, **kwargs)
                return render(request, template, ctx)
            return inner_inner
    return inner


class AsyncAtomicContextManager(Atomic):
    def __init__(self, using=None, savepoint=None, durable=False):
        super().__init__(using, savepoint, durable)
    
    async def __aenter__(self):
        await sync_to_async(super().__enter__)()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await sync_to_async(super().__exit__)(exc_type, exc_value, traceback)


def aatomic(fun, *args, **kwargs):
    async def wrapper(*args, **kwargs):
        async with AsyncAtomicContextManager():
            await fun(*args, **kwargs)
    return wrapper