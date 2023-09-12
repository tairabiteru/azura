from django.db import models
from ...core.models import BaseAsyncModel


class PermissionsObject(BaseAsyncModel):
    SETTINGS = [
        ('+', "ALLOW"),
        ('-', 'DENY')
    ]

    node = models.CharField(max_length=128, help_text="The node of the permissions object. You really should not be touching this.")
    setting = models.CharField(max_length=1, choices=SETTINGS, help_text="The setting of the permissions object. You also should not be touching this.")

    class Meta:
        unique_together = ('node', 'setting')

    def __str__(self):
        return f"{self.setting}{self.node}"
