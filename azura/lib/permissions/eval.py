import typing as t

from .node import Node
from .state import PermissionState


def eval_not_denied(command_node: Node, acl: t.Dict[Node, PermissionState]):
    for acl_node, state in acl.items():
        if command_node in acl_node and state == PermissionState.DENY:
            return False
    return True


def eval_allowed(command_node: Node, acl: t.Dict[Node, PermissionState]):
    for acl_node, state in acl.items():
        if command_node in acl_node and state == PermissionState.ALLOW:
            return True
    return False


def eval_overall(command_node: Node, acl: t.Dict[Node, PermissionState]):
    if not eval_not_denied(command_node, acl):
        return False
    return eval_allowed(command_node, acl)