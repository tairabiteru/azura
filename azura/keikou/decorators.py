from keikou.commands import CommandLike


def command(name, description, **kwargs):
    def decorate(func):
        return CommandLike(func, name, description, **kwargs)
    return decorate
