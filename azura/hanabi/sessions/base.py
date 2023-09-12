from ...ext.ctx import create_timeout_message

import abc
import time


class BaseSession(abc.ABC):
    """
    Session upon which all others are defined.

    This is almost just here as a formality, not going to lie.
    LocalSession and RemoteSession both base this session, which defines
    certain aspects about what constitutes a session, hence, why it's an ABC.

    This class also contains a method and classmethod for serialization/deserialization,
    but these aren't really used. They in theory could be to transmit entire sessions
    over a websocket connection, but Hanabi and Azura both never make use of this.
    """
    def __init__(self, hanabi, guild_id: int, voice_id: int, channel_id: int):
        self.hanabi = hanabi
        self.guild_id: int = guild_id
        self.voice_id: int = voice_id
        self.channel_id: int = channel_id
        self.initialization_time = time.time()

    def to_dict(self):
        """Method to serialize the session."""
        return {
            'guild_id': self.guild_id,
            'voice_id': self.voice_id,
            'channel_id': self.channel_id
        }
    
    @classmethod
    def from_dict(cls, hanabi, data: dict):
        """Classmethod to deserialize from data."""
        return cls(
            hanabi,
            data['guild_id'],
            data['voice_id'],
            data['channel_id']
        )
    
    async def send(self, message=None, embed=None, components=[], delete_after=None):
        """
        Shortcut method to send information to this session's text channel.

        This is used by all methods which transmit information back to the command author.
        """
        if delete_after is None:
            return await self.hanabi.bot.rest.create_message(self.channel_id, message, components=components, embed=embed)
        await create_timeout_message(self.hanabi.bot, self.channel_id, message=message, embed=embed, components=components, timeout=delete_after)