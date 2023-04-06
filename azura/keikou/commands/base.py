from keikou.permissions import GrantLevel, PermissionCheck

import dataclasses
import lightbulb


@dataclasses.dataclass
class CommandLike(lightbulb.CommandLike):
    grant_level: GrantLevel = GrantLevel.IMPLICIT


class KeikouMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        check = PermissionCheck(self)
        self.checks.append(check)
        check.add_to_object_hook(self)

    @property
    def node(self):
        if self.parent is None:
            return f"{self.plugin.name.lower()}.{self.name.lower()}"
        else:
            return f"{self.parent.node}.{self.name.lower()}"

    @property
    def grant_level(self):
        return self._initialiser.grant_level
