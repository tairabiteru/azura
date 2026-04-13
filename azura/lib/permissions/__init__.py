"""Module defining Keikou's permission system

Keikou's permission system is actually based on Minecraft permissions, believe it or not.
The concept at work here is that commands possess a property called a "node". The node of
a command is calculated automatically based upon its position in the entire ecosystem.
As an example, take the /delete command. This command is located in the admin plugin, so
the node would be 'admin.delete'.
Similarly, take the /weather radiosonde command. It is located in the weather plugin, and
the radiosonde command itself is a subcommand of the larger /weather command, so its node
would be 'weather.weather.radiosonde'.

Nodes can also be wildcards. For example, the node 'admin.*' refers to all commands in the
admin plugin. Similarly, 'admin.permissions.*' refers to all subcommands under the /permissions
command.

Finally, a command is hard coded to require an either EXPLICIT or IMPLICIT grant level.
Keikou will permit the execution of commands with an IMPLICIT grant level as long as the
executor's ACL does not explicitly forbid them from executing it.
Likewise, Keikou will DENY the execution of commands with an EXPLICIT grant level unless
their ACL explicitly ALLOWs them to do it.

    * GrantLevel - Enum defining EXPLICIT and IMPLICIT grant levels
    * EXPLICIT - Shortcut to GrantLevel.EXPLICIT
    * IMPLICIT - Shortcut to GrantLevel.IMPLICIT

    * PermissionCheck - Class subclassing a Lightbulb check defining the check callbacks for all Keikou commands
    * CheckFailure - Error thrown when a permissions check fails within Keikou
    * PermissionCheckResult - Class whose object is returned from a permissions check
    * check_acl - Function which evaluates the passed ACL against the passed command to determine if it can be run
    * evaluate_permissions - Function which abstracts the functionality of the previous function to take a user and their roles
    * evaluate_permissions_for_check - Does the same as the above function, but throws a CheckFailure if it fails
    * PermissionsManager - Class whose object is instantiated alongside the bot to allow for global reading of the permissions system
"""


from .node import Node
from .eval import eval_not_denied, eval_allowed, eval_overall
from .errors import PermissionsError, NodeNotFound, AccessIsDenied
from .state import PermissionState


__all__ = [
    eval_allowed,
    eval_not_denied,
    eval_overall,
    Node,
    PermissionState,
    PermissionsError,
    NodeNotFound,
    AccessIsDenied
]