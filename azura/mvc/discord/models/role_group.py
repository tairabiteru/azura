from django.db import models
from .base import DiscordBaseModel
from .role import Role


class RoleGroup(DiscordBaseModel):
    name = models.CharField(max_length=256)
    header_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    watched_roles = models.ManyToManyField(Role, related_name="roles_watched")

    def __str__(self):
        return self.name

    @classmethod
    async def process_event(cls, event):
        async for group in cls.objects.all():
            group = await cls.objects.select_related("header_role").aget(id=group.id)

            async for guild in group.guild.all():
                if event.guild_id != guild.id:
                    return
                break
            else:
                return

            if not event.old_member:
                return
            
            old_roles = set(event.old_member.role_ids)
            new_roles = set(event.member.role_ids)
            
            difference = (old_roles - new_roles).union(new_roles - old_roles)
            if group.header_role.id in difference or not difference:
                return

            should_possess = False
            async for role in group.watched_roles.all():
                if role.id in event.member.role_ids:
                    should_possess = True
            
            if should_possess:
                if group.header_role.id not in event.member.role_ids:
                    await event.member.add_role(group.header_role.id)
            else:
                if group.header_role.id in event.member.role_ids:
                    await event.member.remove_role(group.header_role.id)
        
