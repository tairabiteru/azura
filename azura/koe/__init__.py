import asyncio
import lavasnek_rs

from core.conf import conf
from koe.errors import *
from koe.session import *

import aiohttp

class Koe:
    """
    Implements a Koe object.

    The Koe object is used by the bot themselves to create and destroy
    sessions in a controlled manner.

    This class contains methods prefixed by an _ which are to be effectively
    treated as private. They should not be called outside of the class unless
    you really know what you're doing, as failing to acquire the proper locks
    can result in difficult to troubleshoot race conditions.
    """
    def __init__(self, bot):
        self.bot = bot
        self._sessions = {}
        self._lock = asyncio.Lock()

    # UNSAFE - This should only be called inside of a lock!
    def _can_connect_to_unsafe(self, guild_id):
        for id, session in self._sessions.items():
            if session.guild_id == guild_id and not isinstance(session, RemoteSession):
                return False
        else:
            return True

    async def can_connect_to(self, guild_id):
        async with self._lock:
            return self._can_connect_to_unsafe(guild_id)

    async def get_args(self, ctx):
        user_id = ctx.author.id
        guild_id = ctx.guild_id
        channel_id = ctx.channel_id
        voice_id = None
        for guild_id, state in self.bot.cache.get_voice_states_view().items():
            for uid, voice_state in state.items():
                if user_id == uid:
                    voice_id = voice_state.channel_id

        return (guild_id, voice_id, channel_id)

    async def get_session_from_voice_id(self, voice_id):
        async with self._lock:
            try:
                return self._sessions[voice_id]
            except KeyError:
                raise NoExistingSession(f"An explicit call to get a session for VID {voice_id} was made, but it does not exist.")

    async def get_local_session_from_guild_id(self, guild_id):
        async with self._lock:
            for voice_id, session in self._sessions.items():
                if isinstance(session, LocalSession) and session.guild_id == guild_id:
                    return session
            else:
                raise NoExistingSession(f"An explicit call to get a session for GID {guild_id} was made, but it does not exist.")

    async def create_session(self, guild_id, voice_id, channel_id, bot_name=None):
        async with self._lock:
            if voice_id in self._sessions:
                raise ExistingSession(f"An explicit call to create a session for VID {voice_id} was made, but it already exists.")
        
            if self._can_connect_to_unsafe(guild_id):
                if bot_name is None or bot_name == conf.parent.name:
                    self._sessions[voice_id] = LocalSession(self.bot, guild_id, voice_id, channel_id)
                    await self._sessions[voice_id]._connect()
                    return self._sessions[voice_id]

            if self.bot.type.value != "PARENT":
                raise SessionBusy(f"Attempt to connect to VID {voice_id} failed because the bot is already connected in GID {guild_id}.")
            
            if bot_name is not None:
                session = RemoteSession(bot_name, self.bot, guild_id, voice_id, channel_id)
                await session._connect()
                self._sessions[voice_id] = session
                return session

            for child in conf.children:
                try:
                    session = RemoteSession(child.name, self.bot, guild_id, voice_id, channel_id)
                    await session._connect()
                    self._sessions[voice_id] = session
                    return session
                except SessionBusy:
                    continue
                except ZeroDivisionError:
                    continue
            else:
                raise AllSessionsBusy(f"All bots are occupied in GID {guild_id}.")

    async def get_or_create_session(self, guild_id, voice_id, channel_id):
        try:
            return await self.get_session_from_voice_id(voice_id)
        except NoExistingSession:
            return await self.create_session(guild_id, voice_id, channel_id)

    async def destroy_session(self, voice_id, must_exist=False, send_termination=False):
        async with self._lock:
            try:
                session = self._sessions.pop(voice_id)
                await session._disconnect()
                if send_termination is True:
                    await session._signal_termination_to_parent()
            except KeyError:
                if must_exist is True:
                    raise NoExistingSession(f"An explicit call to destroy the session with VID {voice_id} was made, but it doesn't exist.")
    
    async def handle_voice_state_update(self, event):
        if event.old_state is not None:
            if event.old_state.user_id == self.bot.get_me().id:
                if event.state.channel_id is None:
                    await self.destroy_session(event.old_state.channel_id, send_termination=True)


class EventHandler:
    def __init__(self, bot, *args, **kwargs):
        self.bot = bot

    @property
    def koe(self):
        return self.bot.koe
    
    async def handle_event(self, event):
        try:
            session = await self.koe.get_local_session_from_guild_id(event.guild_id)
            
            if isinstance(event, lavasnek_rs.TrackStart):
                await session.handle_track_start(event)
            elif isinstance(event, lavasnek_rs.TrackFinish):
                await session.handle_track_finish(event)
            elif isinstance(event, lavasnek_rs.PlayerUpdate):
                await session.handle_player_update(event)
        except NoExistingSession:
            return

    async def player_update(self, lavalink, event):
        await self.handle_event(event)

    async def track_start(self, lavalink, event):
        self.bot.logger.info(f"TrackStart event occurred in guild: {event.guild_id}")
        await self.handle_event(event)

    async def track_finish(self, lavalink, event):
        self.bot.logger.info(f"TrackFinish event occurred in guild: {event.guild_id}")
        await self.handle_event(event)

    async def track_exception(self, lavalink, event):
        self.bot.logger.error(f"Track exception event happened on guild: {event.guild_id}")

        # If a track was unable to be played, skip it
        skip = await lavalink.skip(event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)

        if not node:
            return

        if skip and not node.queue and not node.now_playing:
            await lavalink.stop(event.guild_id)
