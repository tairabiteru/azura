from .objects import RepeatMode, EnqueueMode
import inspect
import orjson as json
import typing
import websockets


class Operation:
    """
    Container class for holding operations.

    An operation is an abstraction over a websocket connection.
    Basically, a new operation can be defined with @Operation.define().
    The websocket handler in all bots is set up to parse each websocket
    message as JSON. Further, it expects each incoming message to contain
    a key 'op'. The process classmethod is designed to look for an operation
    which has been defined with the op code stored at the 'op' key.

    As an example, one of the operations defined below is "heartbeat". So the
    heartbeat operation can be invoked by transmitting JSON containing
    {"op": "heartbeat"} over the bot's websocket connection.

    Each operation further defines parameters which are type hinted. This type
    hinting isn't optional, as it allows the processor to automatically determine
    what should be parsed from the JSON and automatically type cast it into the
    correct type.
    
    This all forms a part of Azura I call "interoperations." These are functions
    responsible for allowing Azura to communicate with her children and vice versa.
    The vast majority of these operations are only ever performed by the children, 
    and not the parent. The parent technically supports some of them, but without
    a "commander" to tell the parent to do it, there's not a functional way it can
    happen.
    
    To read more about how this fits into the big picture, have a look at the README.
    """
    OPERATIONS = {}

    @classmethod
    def define(cls, name):
        def inner(func):
            cls.OPERATIONS[name] = func
            return func
        return inner

    @classmethod
    async def process(cls, hanabi, websocket, payload):
        """
        Processor function which selects and then calls
        the correct operation callback.

        This is kind of a heap of garbage...I'm not going to
        defend it or anything, it's just dumb way to do it,
        but it makes the definition of simple operations
        a lot easier.
        """
        operation = payload.pop('op')
        callback = cls.OPERATIONS.get(operation, None)
        if callback is None:
            return await websocket.send(json.dumps({'status': 'NXOP'}))

        args = []
        annotations = inspect.getfullargspec(callback).annotations
        for param_name, cast in annotations.items():
            # HOLY INTROSPECTION BATMAN
            if any([t.__name__ == "NoneType" for t in typing.get_args(cast)]):
                cast = typing.get_args(cast)[0]
                
                if hasattr(cast, "__origin__"):
                    if cast.__origin__.__name__ == "list":
                        t = typing.get_args(cast)[0]
                        cast = lambda x: list(map(t, x))
                    else:
                        raise ValueError
                else:
                    if payload[param_name] is None:
                        args.append(None)
                        continue
            elif hasattr(cast, "__origin__"):
                if cast.__origin__.__name__ == "list":
                    t = typing.get_args(cast)[0]
                    cast = lambda x: list(map(t, x))
                    continue
                else:
                    raise ValueError
    
            args.append(cast(payload[param_name]))

        data = await callback(hanabi, *args)
        try:
            if data:
                return await websocket.send(json.dumps(data))
            return await websocket.send(json.dumps({}))
        except websockets.exceptions.ConnectionClosedOK:
            return


@Operation.define("heartbeat")
async def heartbeat(hanabi, timestamp: int):
    """Simple heartbeat operation."""
    return {'status': 'SUCCESS', 'timestamp': timestamp}


@Operation.define("init-complete")
async def init_complete(hanabi, child_name: str):
    """
    Operation which only the parent recieves. It is sent
    by a child when they come online to inform the parent
    that they are ready to recieve commands over their
    websocket connection.
    """
    ws_uri = hanabi.bot.children[child_name]['ws_uri']
    ws_connection = await websockets.connect(ws_uri)
    ws_uri = hanabi.bot.children[child_name]['ws_connection'] = ws_connection
    hanabi.bot.children[child_name]['is_alive'] = True
    hanabi.bot.logger.info(f"{child_name} reports online.")


@Operation.define("connect")
async def connect(hanabi, guild_id: int, voice_id: int, channel_id: int):
    available = hanabi.bot.available_in(guild_id)
    if not available:
        return {'status': 'UNAVAILABLE'}
    
    session = await hanabi.create_session(guild_id, voice_id, channel_id)
    await session.send("Connected!", delete_after=3)
    return {'status': 'SUCCESS'}


@Operation.define("delete")
async def delete(hanabi, voice_id: int):
    """
    This operation is functionally only executed by
    the parent, and it runs whenever a child destroys a
    session by themselves. (I.E, inactivity timeout or
    a button press.)
    """
    session = await hanabi.delete_session(voice_id)
    action = 'destroyed' if session is not None else 'none'
    return {'status': 'SUCCESS', 'action': action}


@Operation.define("disconnect")
async def disconnect(hanabi, voice_id: int):
    session = await hanabi.get_session(voice_id)
    await session.send("Disconnected", delete_after=3)
    await hanabi.destroy_session(session)
    return {'status': 'SUCCESS'}


@Operation.define("shutdown")
async def shutdown(hanabi):
    hanabi.bot.logger.info("Shutdown signal received")
    await hanabi.bot.kill()


@Operation.define("play")
async def play(hanabi, voice_id: int, title: str, requester: int, position: typing.Optional[int]):
    session = await hanabi.get_session(voice_id)
    await session.play_cmd(title, requester, position)
    return {'status': 'SUCCESS'}


@Operation.define("skip")
async def skip(hanabi, voice_id: int, by: typing.Optional[int], to: typing.Optional[int]):
    session = await hanabi.get_session(voice_id)
    await session.skip(by=by, to=to)


@Operation.define("volume")
async def volume(hanabi, voice_id: int, setting: str):
    session = await hanabi.get_session(voice_id)
    await session.volume_cmd(setting)


@Operation.define("repeat-mode")
async def repeat_mode(hanabi, voice_id: int, mode: RepeatMode):
    session = await hanabi.get_session(voice_id)
    await session.set_repeat_mode(mode)


@Operation.define("enqueue")
async def enqueue(hanabi, voice_id: int, name: str, owner: int, requester: int, shuffle: bool, mode: EnqueueMode, bypass_owner: bool):
    session = await hanabi.get_session(voice_id)
    await session.enqueue_cmd(
        name,
        owner,
        requester,
        shuffle,
        mode,
        bypass_owner
    )

@Operation.define("display-queue")
async def display_queue(hanabi, voice_id: int, amount: typing.Optional[int] = 20):
    session = await hanabi.get_session(voice_id)
    await session.display_queue(amount=amount)


@Operation.define("dequeue")
async def dequeue(hanabi, voice_id: int, positions: typing.Optional[typing.List[int]] = None, requester: typing.Optional[int] = None):
    session = await hanabi.get_session(voice_id)
    await session.dequeue_cmd(positions=positions, requester=requester)