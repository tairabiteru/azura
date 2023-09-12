"""Module defining a Plugin for Keikou

    * Plugin - Basically the same as a Lightbulb plugin, but we define a node property for it
"""

import lightbulb


class Plugin(lightbulb.Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def node(self):
        return self.name
