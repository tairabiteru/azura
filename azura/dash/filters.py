import hikari


filters = []


def filter(func):
    filters.append(func)
    return func


@filter
def commaSeparate(input):
    return "{:,}".format(int(input))


@filter
def repr(value):
    if isinstance(value, hikari.GuildChannel):
        return value.name
    return value


@filter
def id(value):
    if isinstance(value, hikari.GuildChannel) or isinstance(value, hikari.Role):
        return value.id
    return value
