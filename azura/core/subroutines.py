import hikari


def execute_in_background(func):
    loop = hikari.internal.aio.get_or_make_loop()
    return loop.create_task(func)
