import lightbulb


class Plugin(lightbulb.Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def node(self):
        return self.name
