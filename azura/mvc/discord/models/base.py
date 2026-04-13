from django.db import models

from ...core.models import BaseAsyncModel
from ..fields import BaseIDField

from asgiref.sync import sync_to_async
import inspect


def obj_inject_bot(func):
    def wrapper(self, *args, **kwargs):
        bot = kwargs.pop("bot", None)
        kwargs.pop("resolve", False)
        self._bot = bot
        o = func(self, *args, **kwargs)
        o._bot = bot
        return o

    async def awrapper(self, *args, **kwargs):
        bot = kwargs.pop("bot", None)
        resolve = kwargs.pop("resolve", False)
        self._bot = bot
        o = await func(self, *args, **kwargs)

        if isinstance(o, tuple):
            o, _ = o

            o._bot = bot
            if resolve is True:
                await o.resolve_all()
            return o, _
        else:
            o._bot = bot
            if resolve is True:
                await o.resolve_all()
            return o
    if inspect.iscoroutinefunction(func):
        return awrapper
    return wrapper


def qs_inject_bot(func):
    def wrapper(self, *args, **kwargs):
        bot = kwargs.pop("bot", None)
        only_valid = kwargs.pop("only_valid", [])
        resolve = kwargs.pop("resolve", False)
        self._bot = bot
        qs = func(self, *args, **kwargs)
        qs._bot = bot
        return DiscordQuerySet.from_queryset(qs, only_valid=only_valid, resolve=resolve)

    async def awrapper(self, *args, **kwargs):
        bot = kwargs.pop("bot", None)
        only_valid = kwargs.pop("only_valid", [])
        resolve = kwargs.pop("resolve", False)
        self._bot = bot
        qs = await func(self, *args, **kwargs)
        qs._bot = bot
        return DiscordQuerySet.from_queryset(qs, only_valid=only_valid, resolve=resolve)
    
    if inspect.iscoroutinefunction(func):
        return awrapper
    return wrapper


class DiscordQuerySet(models.query.QuerySet):
    def __init__(self, *args, **kwargs):
        self._bot = kwargs.pop('bot', None)
        self.only_valid = kwargs.pop('only_valid', [])
        self.resolve = kwargs.pop('resolve', False)
        super().__init__(*args, **kwargs)
    
    def attach_bot_to(self, obj):
        obj._bot = self._bot
        return obj
    
    def __iter__(self):
        self._fetch_all()
        for item in self._result_cache:
            if hasattr(item, "_bot"):
                item._bot = self._bot
                if self.resolve is True:
                    self.item.resolve_all()
            yield item
    
    def __aiter__(self):
        async def generator():
            await sync_to_async(self._fetch_all)()
            for item in self._result_cache:
                item = self.attach_bot_to(item)
                if self.resolve is True:
                    await item.resolve_all()
                    if any([isinstance(item._resolved[field], Exception) for field in self.only_valid]):
                        continue
                yield item
        return generator()


def inject_bot(func):
    def inner(self, *args, **kwargs):
        self._bot = kwargs.pop('bot', None)
        self.only_valid = kwargs.pop('only_valid', [])
        self.resolve = kwargs.pop('resolve', False)
        return func(self, *args, **kwargs)
    return inner


class DiscordBaseManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self._bot = kwargs.pop('bot', None)
        self.only_valid = kwargs.pop('only_valid', [])
        self.resolve = kwargs.pop('resolve', False)
        super().__init__(*args, **kwargs)

    @inject_bot
    def filter(self, *args, **kwargs):
        return super().filter(*args, **kwargs)
    
    @inject_bot
    def all(self, *args, **kwargs):
        return super().all(*args, **kwargs)
    
    @obj_inject_bot
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)
    
    @obj_inject_bot
    async def aget(self, *args, **kwargs):
        return await super().aget(*args, **kwargs)
    
    @obj_inject_bot
    def get_or_create(self, *args, **kwargs):
        return super().get_or_create()
    
    @obj_inject_bot
    async def aget_or_create(self, *args, **kwargs):
        return await super().aget_or_create(*args, **kwargs)
    
    @inject_bot
    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **kwargs)
    
    def get_queryset(self):
        return DiscordQuerySet(model=self.model, using=self._db, hints=self._hints, bot=self._bot, only_valid=self.only_valid, resolve=self.resolve)


class DiscordBaseModel(BaseAsyncModel):
    objects = DiscordBaseManager()

    def __init__(self, *args, **kwargs):
        self._bot  = kwargs.pop('bot', None)
        self._resolved = {}

        super().__init__(*args, **kwargs)

    class Meta:
        abstract = True
    
    def attach_bot(self, bot):
        self._bot = bot
    
    async def aresolve_all(self, bot=None):
        if bot is not None:
            self.attach_bot(bot)

        for name in self._get_field_expression_map(self._meta).keys():
            if name == "pk":
                continue
            field = getattr(self.__class__, name)
            if isinstance(field, property):
                continue
            else:
                field = field.field
            if isinstance(field, BaseIDField):
                self._resolved[name] = await field.aresolve(self.bot, getattr(self, name))
    
    def resolve_all(self, bot=None):
        if bot is not None:
            self.attach_bot(bot)
        
        for name in self._get_field_expression_map(self._meta).keys():
            if name == "pk":
                continue
            field = getattr(self.__class__, name).field
            if isinstance(field, BaseIDField):
                self._resolved[name] = field.resolve(self.bot, getattr(self, name))
    
    async def aresolve(self, field_name, bot=None):
        if bot is not None:
            self.attach_bot(bot)

        field = getattr(self.__class__, field_name).field
        if not isinstance(field, BaseIDField):
            raise ValueError(f"The field '{field_name}' is not a Discord ID.")
        return await field.aresolve(self.bot, getattr(self, field_name))
    
    def resolve(self, field_name, bot=None):
        if bot is not None:
            self.attach_bot(bot)
        
        field = getattr(self.__class__, field_name).field
        if not isinstance(field, BaseIDField):
            raise ValueError(f"The field '{field_name}' is not a Discord ID.")
        return field.resolve(self.bot, getattr(self, field_name))

    @property
    def bot(self):
        if self._bot is None:
            raise ValueError("Bot attribute not set.")
        return self._bot