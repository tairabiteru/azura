import anytree
import lightbulb

from .state import PermissionState
from .errors import NodeNotFound
from ...mvc.discord.models.permissions import PermissionsObject


class Node(anytree.Node):
    _root = None

    @classmethod
    def build_from_client(
        cls,
        client: lightbulb.Client
        ):
        root = cls("*")

        for group in client._registered_commands.keys():
            if isinstance(group, lightbulb.Group):
                cls.build_from_group(root, group)
            else:
                cls.build_from_command(root, group)

        cls._root = root
        return root
    
    @classmethod
    def build_from_group(cls, parent, group):
        node = cls(group.name, parent=parent)

        for command in group._commands.values():
           if isinstance(command, lightbulb.SubGroup):
               cls.build_from_group(node, command)
           else:
               cls.build_from_command(node, command)

        return parent
    
    @classmethod
    def build_from_command(cls, parent, command):
        return cls(command._command_data.name.lower().replace(" ", "_"), parent=parent)
    
    def __repr__(self):
        if self.parent is not None:
            return f"{self.parent}.{self.name}"
        return "*"

    @property
    def value(self):
        return self.__repr__()

    @property
    def root(self):
        if self.__class__._root is None:
            raise ValueError("The root node has not been set.")
        return self.__class__._root
    
    def __contains__(self, other):
        return self.value in other.value

    def render(self):
        return anytree.RenderTree(self)
    
    def get_node_from_command(self, command):
        node = command._command_data.name.replace(" ", "_").lower()
        if command._command_data.parent is not None:
            node = self.get_node_from_command(command._command_data.parent).value + "." + node
            return self.root.get_node(node)
        else:
            return self.root.get_node(f"*.{node}")
        
    
    def get_node(self, name):
        if name == "*":
            return self.root

        for node in self.children:
            if name == node.value:
                return node
            elif name.startswith(node.value):
                try:
                    return node.get_node(name)
                except NodeNotFound:
                    pass
        raise NodeNotFound
    
    async def get_obj(self, state: PermissionState):
        setting = "+" if state == PermissionState.ALLOW else "-"
        obj, _ = await PermissionsObject.objects.aget_or_create(node=self.value, setting=setting)
        return obj

    async def ensure_objects(self):
        await self.get_obj(PermissionState.ALLOW)
        await self.get_obj(PermissionState.DENY)
        
        for child in self.children:
            await child.ensure_objects()
    
    async def delete_unused(self):
        async for node in PermissionsObject.objects.all():
            try:
                self.get_node(node.node)
            except NodeNotFound:
                await node.adelete()

            

