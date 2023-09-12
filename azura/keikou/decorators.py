"""Module defining the command decorator for Keikou

    * command - Decorator defining a command in Keikou. Similar to Lightbulb's decorator
"""


from .commands import CommandLike


def command(name, description, **kwargs):
    def decorate(func):
        return CommandLike(func, name, description, **kwargs)
    return decorate
