import asyncio
from django.utils.decorators import sync_and_async_middleware
from django.http import HttpRequest

from ...core.bot import Bot


class DiscordAwareHttpRequest(HttpRequest):
    def __init__(self, request: HttpRequest, bot: Bot):
        self._request = request
        self.bot = bot
        
        self.GET = self._request.GET
        self.POST = self._request.POST
        self.COOKIES = self._request.COOKIES
        self.META = self._request.META
        self.FILES = self._request.FILES
        
        self.path = self._request.path
        self.path_info = self._request.path_info
        self.method = self._request.method
        self.resolver_match = self._request.resolver_match
        self.content_type = self._request.content_type
        self.content_params = self._request.content_params
        
        if hasattr(self._request, "session"):
            self.session = self._request.session
        if hasattr(self._request, "user"):
            self.user = self._request.user
        if hasattr(self._request, "_messages"):
            self._messages = self._request._messages  # type: ignore


@sync_and_async_middleware
def BotInjectorMiddleware(get_response):
    loop = asyncio.get_running_loop()

    if asyncio.iscoroutinefunction(get_response):
        async def a_middleware(request):
            request = DiscordAwareHttpRequest(request, loop.bot) # type: ignore
            return await get_response(request)
        return a_middleware
    else:
        def s_middleware(request):
            request = DiscordAwareHttpRequest(request, loop.bot) # type: ignore
            return get_response(request)
        return s_middleware