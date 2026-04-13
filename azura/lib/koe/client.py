from __future__ import annotations
import asyncio
import hikari
import ongaku

from .errors import NXSession, InvalidState, EXSession


class KoeClient:
    def __init__(
        self,
        bot: hikari.GatewayBot,
        ongaku: ongaku.Client
    ):
        self.bot = bot
        self.ongaku = ongaku
        self._sessions: dict[hikari.Snowflake, KoeSession] = {}
        
        self.session_lock = asyncio.Lock()
    
    def _get_session_by_gid_unsafe(self, guild_id: hikari.Snowflake) -> KoeSession | None:
        for session in self._sessions.values():
                if session.guild_id == guild_id:
                    return session
        else:
            return None
        
    async def get_session_by_gid(self, guild_id: hikari.Snowflake, unsafe: bool=False) -> KoeSession | None:
        if unsafe is True:
            return self._get_session_by_gid_unsafe(guild_id)
            
        async with self.session_lock:
            return self._get_session_by_gid_unsafe(guild_id)
    
    async def get_session_by_vid(self, voice_id: hikari.Snowflake, unsafe: bool=False) -> KoeSession | None:
        if unsafe is True:
            return self._sessions.get(voice_id, None)
        
        async with self.session_lock:
            return self._sessions.get(voice_id, None)
        
    async def create_session(
        self,
        guild_id: hikari.Snowflake,
        voice_id: hikari.Snowflake,
        channel_id: hikari.Snowflake,
        connect: bool=False
    ) -> KoeSession:
        async with self.session_lock:
            gid_sesh = await self.get_session_by_gid(guild_id, unsafe=True)
            vid_sesh = await self.get_session_by_vid(voice_id, unsafe=True)
            if gid_sesh or vid_sesh:
                raise EXSession(voice_id, "create_session")
            
            session = KoeSession(self, guild_id, voice_id, channel_id)
            if connect is True:
                await session.join()
            self._sessions[voice_id] = session
            return session
    
    async def del_session(self, vid: hikari.Snowflake | None=None, gid: hikari.Snowflake | None=None) -> KoeSession:
        if vid is None and gid is None:
            raise ValueError("Must provide one of either vid or gid.")
        if vid is not None and gid is not None:
            raise ValueError("Must provide either vid or gid, not both.")
        
        async with self.session_lock:
            session = None
            
            if vid is not None:
                session = self._sessions.pop(vid, None)
            if gid is not None:
                for session in self._sessions.values():
                    if session.guild_id == gid:
                        session = self._sessions.pop(session.voice_id, None)
                        break
            
            if session is None:
                id = vid or gid
                assert id is not None
                raise NXSession(id, "del_session")
            
            await session.destroy()
            return session
        

class KoeSession:
    def __init__(
        self,
        koe: KoeClient,
        guild_id: hikari.Snowflake,
        voice_id: hikari.Snowflake,
        channel_id: hikari.Snowflake
    ):
        self.koe = koe
        self.guild_id = guild_id
        self.voice_id = voice_id
        self.channel_id = channel_id

        self.lock = asyncio.Lock()
        self._player = ongaku.ControllablePlayer | None
    
    @property
    def bot(self) -> hikari.GatewayBot:
        return self.koe.bot
    
    @property
    def player(self) -> ongaku.ControllablePlayer:
        assert isinstance(self._player, ongaku.ControllablePlayer)
        return self._player
    
    async def join(self) -> None:
        async with self.lock:
            voice = self.bot.voice.connections.get(self.guild_id)
        
            if voice is not None:
                raise InvalidState(self.voice_id, "KoeSession.join")
        
            self._connection = await self.bot.update_voice_state(
                self.guild_id,
                self.voice_id
            )
            self._player = self.koe.ongaku.create_player(self.guild_id)
    
    async def destroy(self) -> None:
        async with self.lock:
            states = self.bot.cache.get_voice_states_view()

            for id in states.keys():
                if id == self.guild_id:
                    break
            else:
                raise InvalidState(self.voice_id, "KoeSession.destroy")

            await self.bot.update_voice_state(self.guild_id, None)
            await self.koe.ongaku.delete_player(self.guild_id)
            self._connection = None
        