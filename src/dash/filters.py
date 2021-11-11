filters = []


def filter(func):
    filters.append(func)
    return func


@filter
def commaSeparate(input):
    return "{:,}".format(int(input))
