import sanic


def remove_code_param(func):
    """Define decorator that removes code parameter from a route."""
    def wrapper(request):
        if 'code' in request.url and '?' in request.url:
            params = request.url.split("?")[-1].split("&")
            params = list([param for param in params if 'code=' not in param])
            return sanic.response.redirect(f"{request.url.split('?')[0]}?{'&'.join(params)}")
        return func(request)
    return wrapper
