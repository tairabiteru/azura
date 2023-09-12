from .utils import is_optional

from dataclasses import dataclass
import enum
import orjson as json
import typing
from inspect import signature


class Serializable:
    """
    Defines a JSON serializable object.

    This was originally going to be apart of a grand scheme to
    allow Azura to transmit entire objects back and forth over a
    websocket connection, but as it turns out, that's dumb. It's possible,
    just...not at all efficient. But this still remains sort of because
    it's useful for deserializing information coming in from Lavalink. That's
    what it was originally designed for, but I took it a few steps further.
    Alas, for no good reason it seems.

        "But nobody actually knew how to build a suspension 
    bridge, so they got halfway through it and then just added 
    extra support columns to keep the thing standing, but they left
    the suspension cables because they're still sort of holding up
    parts of the bridge. Nobody knows which parts, but everybody's
    pretty sure they're important parts." - Peter Welch
    """
    @classmethod
    def from_dict(cls, data: dict):
        native_args = {}
        new_args = {}
        
        for name, value in data.items():
            hints = typing.get_type_hints(cls)
            try:
                subclass = hints[name]
            except KeyError:
                print(data)
                print(hints)
                print(cls)

            if is_optional(subclass):
                subclass = typing.get_args(subclass)[0]

            if issubclass(subclass, Serializable) and isinstance(value, dict):
                value = subclass.from_dict(value)

            if name in signature(cls).parameters:
                native_args[name] = value
            else:
                new_args[name] = value
        
        obj = cls(**native_args)

        for name, value in new_args.items():
            setattr(obj, name, value)
        return obj

    @classmethod
    def from_json(cls, data: str):
        return cls.from_dict(json.loads(data))

    def to_dict(self) -> dict:
        out = {}
        for name, value in self.__dict__.items():
            if isinstance(value, Serializable):
                value = value.to_dict()
            out[name] = value
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict())



@dataclass
class PlayerState(Serializable):
    time: int
    connected: bool
    ping: int
    position: typing.Optional[int] = None


@dataclass
class Memory(Serializable):
    free: int
    used: int
    allocated: int
    reservable: int


@dataclass
class Cpu(Serializable):
    cores: int
    system_load: float
    lavalink_load: float


@dataclass
class FrameStats(Serializable):
    sent: int
    nulled: int
    deficit: int


@dataclass
class Stats(Serializable):
    players: int
    playing_players : int
    uptime: int
    memory: Memory
    cpu: Cpu
    frame_stats: typing.Optional[FrameStats] = None


@dataclass
class TrackInfo(Serializable):
    identifier: str
    is_seekable: bool
    author: str
    length: int
    is_stream: bool
    position: int
    title: str
    uri: str
    artwork_url: str
    isrc: str
    source_name: str


@dataclass
class Track(Serializable):
    encoded: str
    info: TrackInfo
    plugin_info: Serializable
    requester: typing.Optional[int] = None
    begin_at: typing.Optional[int] = 0
    end_at: typing.Optional[int] = None

    def __repr__(self):
        return f"<Track: '{self.info.title}'>"


class Severity(enum.Enum):
    COMMON = 0
    SUSPICIOUS = 1
    FAULT = 2


@dataclass
class TrackException(Serializable):
    severity: typing.Optional[Severity]
    cause: typing.Optional[str]
    message: typing.Optional[str] = None


class HttpMethod(enum.Enum):
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class VoiceState(Serializable):
    token: str
    endpoint: str
    session_id: str


@dataclass
class Player(Serializable):
    guild_id: int
    track: typing.Optional[Track]
    volume: int
    paused: bool
    state: PlayerState
    voice: VoiceState
    filters: dict


class RepeatMode(enum.Enum):
    NONE = "None"
    ONE = "One"
    ALL = "All"


class EnqueueMode(enum.Enum):
    """
    Enum representing different enqueueing modes.

    - FIFO: First In, First Out. Songs enqueued in this manner are placed
    at the bottom of the queue.

    - LIFO: Last In, First Out. Songs enqueued in this manner are placed
    at the top of the queue.

    - RANDOM: Songs enqueued in this manner are placed at random intervals
    throughout the queue.
    
    - INTERLACE: Songs enqueued in this manner are placed at regular intervals
    along the queue. The interval is determined by the number of unique requesters
    presently in the queue.
    """
    FIFO = "FIFO"
    LIFO = "LIFO"
    RANDOM = "RANDOM"
    INTERLACE = "INTERLACE"