import enum


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


class RepeatMode(enum.Enum):
    """
    Enum represeting different repeat modes:

    - NONE: No repeating. The queue will advance to the next song
    until the queue has been completed, at which point, playback will stop.

    - ONE: Repeat a single song. The queue will play the current song until it
    ends, at which point, the same track will be started over, repeating indefinitely.

    - ALL: Repeat all songs. The queue will advance to the next song until the
    queue is completed, at which point, playback will start over at the beginning
    of the queue.
    """
    NONE = "None"
    ONE = "One"
    ALL = "All"


class SessionState(enum.Enum):
    """
    Enum represeting the different states a session can be in.

    - NEW: A newly created session. Nothing has been played yet.
    - STOPPED: Playback has been manually halted.
    - PLAYING: Playback is actively happening.
    - ENDED: Playback has completed of its own accord.
    - PAUSED: Playback has been paused.
    - SKIPPED: Playback is in the process of being skipped.
    - DISCONNECTED: Playback has stopped, and the session has been disconnected.
    """
    NEW = "New"
    STOPPED = "Stopped"
    PLAYING = "Playing"
    ENDED = "Ended"
    PAUSED = "Paused"
    SKIPPED = "Skipped"
    DISCONNECTED = "Disconnected"