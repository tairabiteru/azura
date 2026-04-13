import hikari
import hikari.channels

from .models import User, Guild, Channel, Role


def handle_events(*event_classes):
    def inner(func):
        async def wrapper(event):
            if not any([isinstance(event, event_cls) for event_cls in event_classes]):
                raise ValueError(f"Event {event} is not an instance of any: {event_classes}")
            return await func(event)
        return wrapper
    return inner


class DiscordEventHandler:
    @staticmethod
    @handle_events(hikari.GuildEvent)
    async def handle_guild_event(event):
        if isinstance(event, hikari.GuildJoinEvent) or isinstance(event, hikari.GuildLeaveEvent):
            await DiscordEventHandler.run_model_update(event.app)
    
    @staticmethod
    @handle_events(hikari.ChannelEvent)
    async def handle_channel_event(event):
        if isinstance(event, hikari.GuildChannelDeleteEvent):
            channel = await Channel.objects.aget(id=event.channel_id)
            await channel.adelete()
        if isinstance(event, hikari.GuildChannelCreateEvent):
            guild = await Guild.objects.aget(id=event.guild_id)
            channel = Channel(id=event.channel_id, guild=guild)
            await channel.asave()
    
    @staticmethod
    @handle_events(hikari.MemberEvent)
    async def handle_member_event(event):
        if isinstance(event, hikari.MemberCreateEvent):
            try:
                await User.objects.aget(id=event.user.id)
            except User.DoesNotExist:
                user = User(id=event.user.id)
                await user.asave()

    @staticmethod
    @handle_events(hikari.RoleEvent)
    async def handle_role_event(event):
        if isinstance(event, hikari.RoleCreateEvent):
            guild = await Guild.objects.aget(id=event.guild_id)
            role = Role(id=event.role_id, guild=guild)
            await role.asave()
        if isinstance(event, hikari.RoleDeleteEvent):
            role = await Role.objects.aget(id=event.role_id)
            await role.adelete()

    @staticmethod
    async def run_model_update(bot):    
        guilds = []
        async for guild in bot.rest.fetch_my_guilds():
            async for member in bot.rest.fetch_members(guild):
                _, _ = await User.objects.aget_or_create(id=member.id)
                
            guilds.append(guild.id)
            try:
                await Guild.objects.aget(id=guild.id)
            except Guild.DoesNotExist:
                guild = Guild(id=guild.id)
                await guild.asave()
        
        async for guild in Guild.objects.all():
            try:
                await bot.rest.fetch_guild(guild.id)
            except (hikari.UnauthorizedError, hikari.NotFoundError):
                async for channel in Channel.objects.filter(guild_id=guild.id):
                    bot.logger.warning(f"Deleting channel ID: {channel.id} since its guild is missing.")
                    await channel.adelete()
                async for role in Role.objects.filter(guild_id=guild.id):
                    bot.logger.warning(f"Deleting role ID: {role.id} since its guild is missing.")
                    await role.adelete()
                bot.logger.warning(f"Deleting Guild ID: {guild.id} since it can no longer be resolved.")
                await guild.adelete()

        channels = []
        for _, channel in bot.cache.get_guild_channels_view().items():
            channels.append(channel.id)
            try:
                await Channel.objects.aget(id=channel.id)
            except Channel.DoesNotExist:
                if channel.type == hikari.channels.ChannelType.GUILD_TEXT:
                    type = 'GUILD_TEXT'
                elif channel.type == hikari.channels.ChannelType.GUILD_VOICE:
                    type = 'GUILD_VOICE'
                else:
                    continue
                guild, _ = await Guild.objects.aget_or_create(id=channel.guild_id, bot=bot, resolve=False)
                channel = Channel(id=channel.id, type=type, guild=guild)
                await channel.asave()
        
        guild_channel_mapping = {}
        async for channel in Channel.objects.all():
            guild = (await Channel.objects.select_related('guild').aget(id=channel.id)).guild
            try:
                if channel.id not in guild_channel_mapping[str(guild.id)]:
                    bot.logger.warning(f"Deleting channel ID: {channel.id} since it can no longer be resolved.")
                    await channel.adelete()
            except KeyError:
                try:
                    await bot.rest.fetch_guild(guild.id)

                    guild_channel_mapping[str(guild.id)] = list([c.id for c in (await bot.rest.fetch_guild_channels(guild.id))])
                    if channel.id not in guild_channel_mapping[str(guild.id)]:
                        bot.logger.warning(f"Deleting channel ID: {channel.id} since it can no longer be resolved.")
                        await channel.adelete()
                except hikari.errors.NotFoundError:
                    bot.logger.warning(f"Deleting channel ID: {channel.id} since its guild is missing.")
                    await channel.adelete()                
        
        roles = []
        for _, role in bot.cache.get_roles_view().items():
            roles.append(role.id)
            try:
                await Role.objects.aget(id=role.id)
            except Role.DoesNotExist:
                guild = await Guild.objects.aget(id=role.guild_id, bot=bot, resolve=False)
                role = Role(id=role.id, guild_id=role.guild_id)
                await role.asave()
        
        guild_role_mapping = {}
        async for role in Role.objects.all():
            guild = (await Role.objects.select_related('guild').aget(id=role.id)).guild
            try:
                if role.id not in guild_role_mapping[str(guild.id)]:
                    bot.logger.warning(f"Deleting role ID: {role.id} since it was not in the cache.")
                    await role.adelete()
            except KeyError:
                try:
                    await bot.rest.fetch_guild(guild.id)
                
                    guild_role_mapping[str(guild.id)] = list([r.id for r in (await bot.rest.fetch_roles(guild.id))])
                    if role.id not in guild_role_mapping[str(guild.id)]:
                        bot.logger.warning(f"Deleting role ID: {role.id} since it was not in the cache.")
                        await role.adelete()
                except hikari.errors.NotFoundError:
                    bot.logger.warning(f"Deleting role ID: {role.id} since its guild is missing.")
                    await role.adelete()
        
        await bot.permissions_root.ensure_objects()
        await bot.permissions_root.delete_unused()