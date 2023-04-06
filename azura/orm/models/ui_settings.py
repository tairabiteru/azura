class UISetting:
    def __init__(self, name, attr, type, current, description, options=[], maxlength=None, pattern=None, select_multiple=False):
        self.attr = attr
        self.name = name
        self.description = description
        self.type = type
        self.current = current
        self.options = options
        self.pattern = pattern
        self.maxlength = maxlength
        self.select_multiple = select_multiple
