from koe.enums import EnqueueMode, RepeatMode

import abc
import aiohttp
import hikari
import uuid


class Session(abc.ABC):
    """
    Base implementation of a Session.

    The session is at the core of how Koe works. A "session" represents
    an instance of connection, control, and playback to a voice channel.
    This can either be a LocalSession, or a RemoteSession, depending on which
    bot handled the request.

    Whenever a command like `/connect` is executed, the parent bot will first
    ask its Koe instance to try to obtain a session. The Koe instance does this by
    first checking for an existing matching session. If one exists which the parent
    is currently handling, then a LocalSession object is returned, and methods are
    called upon it. If however one which is local to the parent bot doesn't exist, 
    then a RemoteSession object is returned. A RemoteSession has much the same types
    of forward facing method as the LocalSession. The only difference is, instead 
    of directly invoking the requested action, a web endpoint is accessed conveying
    this same information to a child bot. The child then instantiates their own
    LocalSession, and the RemoteSession on the parent acts as a pipeline through
    which the parent can communicate with the child.

    This is what a Session represents, and LocalSession and RemoteSession both implement the
    abstract methods contained herein.
    """
    def __init__(self, bot, guild_id, voice_id, channel_id):
        self.bot = bot
        self.id = uuid.uuid4().hex
        self.guild_id = guild_id
        self.voice_id = voice_id
        self.channel_id = channel_id

    @property
    def serialized(self):
        return {
            'guild_id': self.guild_id,
            'voice_id': self.voice_id,
            'channel_id': self.channel_id
        }

    @property
    def lavalink(self):
        return self.bot.lavalink

    @property
    def koe(self):
        return self.bot.koe
    
    async def _post(address, data):
        async with aiohttp.ClientSession() as session:
            async with session.post(address, json=data, headers={'Content-Type': 'application/json'}) as response:
                response = await response.json()
        return response
    
    @abc.abstractmethod
    async def display_playback(self):
        """
        This method should cause the playback message and controls
        to be displayed to the user. If called while they already exist,
        they should be re-created.
        """
        ...
    
    @abc.abstractmethod
    async def display_queue(self):
        """
        This method should cause the queue embed to be displayed.
        """
        ...
    
    @abc.abstractmethod
    async def enqueue(self, requester: hikari.User, playlist: str, shuffle: bool=False, mode: str=EnqueueMode.FIFO, user: hikari.User=None):
        ...
    
    @abc.abstractmethod
    async def pause(self):
        ...

    @abc.abstractmethod
    async def play(self, requester: hikari.User, query: str, position: int=-1):
        """
        This method should enqueue the song specified by the query in the specified
        position. This method should also handle the process of inquiry which takes
        place when a user's query returns more than one result.
        """
        ...

    @abc.abstractmethod
    async def set_repeat_mode(self, setting: RepeatMode):
        ...
    
    @abc.abstractmethod
    async def set_volume(self, user, setting=None, increment=None):
        ...
    
    @abc.abstractmethod
    async def skip(self, requester: hikari.User, to: int=None, by: int=None):
        """
        This method should cause the player to skip to a track, or by a number
        of tracks. The requester for the skip is also required to relay back
        who initiated the skip.
        """
        ...
