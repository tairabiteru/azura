"""
Hooks for Lightbulb 3.

Hooks are functions and coroutines which can be added to the execution
pipeline of a lightbulb command that can alter or interrupt execution.
All of the functions in here are components of Elysia's permissions system,
as the hooks here are designed to halt execution of a command if the permissions
state is incorrect.
"""
from .permissions import require_granted, require_not_denied, require_owner
from .voice import require_user_in_voice, require_existing_session, require_no_session, SessionError


__all__ = [
    'require_granted',
    'require_not_denied',
    'require_owner',
    'require_user_in_voice',
    'require_existing_session',
    'require_no_session',
    'SessionError'
]