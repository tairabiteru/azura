"""
Components for aspects of Elysia's operation.

Components are what Discord calls the menus, select boxes, buttons,
and other things associated with an application command. All of the
things defined here serve that purpose in some way or another.
"""
from .pagination import pagify
from .validation import Validation, validate


__all__ = [
    "Validation",
    "validate",
    "pagify",
]
