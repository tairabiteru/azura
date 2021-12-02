from ext.utils import strfdelta

import asyncio
import datetime
import enum
import hikari
import urllib


class Repeat(enum.Enum):
    NONE = 0
    ONE = 1
    ALL = 2


class NowPlayingMessage:
    """
    Implement the now playing message.

    Part of the trouble with Azura is that the message she displays is ultimately
    complex, as well as being full of threaded bullshit. To manipulate the
    message correctly is to have threads interact with other threads which
    interact with this thread due to changes in the other threads.

    It's garbage.
    But unfortunately, it's what's necessary in order to implement a fancy
    interface that people can poke at instead of typing commands like cool kids do.

    ...

    Attributes
    ----------
    session: typing.Union[LocalKoeSession, ChildKoeSession]
        The session to which this message is attached.
    stream: hikari.api.event_manager.EventStream
        The event stream attached to the interaction listener, if any.

    _lock: asyncio.Lock
        A lock used to synchronize message changes and closures.
    _msg: hikari.messages.Message
        The internal message object which the class manipulates.
    _valid: bool
        A boolean saying whether or not the message is still valid.
        This gets set to False when NowPlayingMessage.close() is called.

    Methods
    -------
    getTimeline(position, length)
        Generate the current player timeline.
    getEmbed(position=None)
        Generate the current embed.
    getActionRows()
        Generate the interaction component rows.
    interactionListener()
        Task which listens and responds to interaction events.
    isValid()
        Read method to access validity of message externally.
    generate()
        Create and initialize the message.
    update(event=None)
        Update the message.
    close()
        End interaction with the message.
    """
    def __init__(self, session):
        """
        Construct attributes for message.

        Parameters
        ----------
        session: typing.Union[LocalKoeSession, ChildKoeSession]
            The session that this message is attached to.

        """
        self.session = session
        self.stream = None

        self._lock = asyncio.Lock()
        self._msg = None
        self._valid = False

    def getTimeline(self, position, length):
        """
        Create the track timeline from position and length.

        Parameters
        ----------
        position: int
            The current position to render in seconds.
        length: int
            The total length to render against the position in seconds.

        Returns
        -------
        str

        """
        LENGTH = 40

        percent = position / length
        complete = "━" * int(percent * LENGTH)
        left = "╸" * int(LENGTH - (percent * LENGTH))
        timeline = f"[{complete}➤{left}]"

        position = strfdelta(datetime.timedelta(seconds=position), '{%H}:{%M}:{%S}')
        length = strfdelta(datetime.timedelta(seconds=length), '{%H}:{%M}:{%S}')
        return f"{position} `{timeline}` {length}"

    async def getEmbed(self, position=None):
        """
        Create the message embed.

        Parameters
        ----------
        position: typing.Optional[int]
            The current position to render in seconds. If not specified, the
            timeline will not be rendered.

        Returns
        -------
        hikari.embeds.Embed

        """
        node = await self.session.bot.lavalink.get_guild_node(self.session.gid)
        try:
            requester = self.session.bot.cache.get_member(self.session.gid, node.now_playing.requester)
        except TypeError:
            requester = None
        current = node.now_playing

        if "http" in current.track.info.uri:
            embed = hikari.embeds.Embed(
                title=current.track.info.title,
                url=current.track.info.uri
            )
        else:
            embed = hikari.embeds.Embed(
                title=current.track.info.title
            )

        if position is not None:
            timeline = self.getTimeline(position / 1000, length=current.track.info.length / 1000)
        else:
            timeline = ""

        state = await self.session.state()
        volume = await self.session.volumeLevel()
        embed.description = f"**{state}**\n{timeline}"
        embed.add_field(name="Author", value=current.track.info.author, inline=True)
        if requester is not None:
            embed.add_field(name="Requester", value=requester.username, inline=True)
        embed.add_field(name="Volume", value=f"{volume}%", inline=True)

        if "youtube.com" in current.track.info.uri:
            url = urllib.parse.urlparse(node.now_playing.track.info.uri)
            query = urllib.parse.parse_qs(url.query)
            embed.set_image(f"https://img.youtube.com/vi/{query['v'][0]}/0.jpg")
        return embed

    async def getActionRows(self):
        """
        Generate the interaction button rows.

        Returns
        -------
        typing.List[hikari.api.special_endpoints.ActionRowBuilder]

        """
        rows = []

        row = self.session.bot.rest.build_action_row()
        if not (await self.session.queue.isStart()):
            row.add_button(hikari.ButtonStyle.SECONDARY, "⏮️").set_label("⏮️").add_to_container()

        row.add_button(hikari.ButtonStyle.DANGER, "⏹️").set_label("⏹️").add_to_container()

        paused = await self.session.isPaused()
        pbutton = "▶️" if paused else "⏸️"
        row.add_button(hikari.ButtonStyle.SECONDARY, pbutton).set_label(pbutton).add_to_container()

        if not (await self.session.queue.isEnd()):
            row.add_button(hikari.ButtonStyle.SECONDARY, "⏭️").set_label("⏭️").add_to_container()

        rows.append(row)

        row = self.session.bot.rest.build_action_row()
        if (await self.session.volumeLevel()) > 0:
            row.add_button(hikari.ButtonStyle.SECONDARY, "🔉").set_label("🔉").add_to_container()
        if (await self.session.volumeLevel()) < 1000:
            row.add_button(hikari.ButtonStyle.SECONDARY, "🔊").set_label("🔊").add_to_container()

        rows.append(row)

        row = self.session.bot.rest.build_action_row()
        mode = await self.session.repeatMode()
        if mode == Repeat.ALL:
            row.add_button(hikari.ButtonStyle.PRIMARY, "🔁").set_label("🔁").add_to_container()
        else:
            row.add_button(hikari.ButtonStyle.SECONDARY, "🔁").set_label("🔁").add_to_container()
        if mode == Repeat.ONE:
            row.add_button(hikari.ButtonStyle.PRIMARY, "🔂").set_label("🔂").add_to_container()
        else:
            row.add_button(hikari.ButtonStyle.SECONDARY, "🔂").set_label("🔂").add_to_container()

        rows.append(row)

        return rows

    async def interactionListener(self):
        """
        Listen for interaction events.

        This will block until an event happens, or until the stream is closed.
        Meant to be run as a separate task.

        Returns
        -------
        None

        """
        cont = True

        while cont:
            cont = False

            self.stream = self.session.bot.stream(hikari.InteractionCreateEvent, timeout=None).filter(
                lambda event: (
                    isinstance(event.interaction, hikari.ComponentInteraction)
                    and event.interaction.message.id == self._msg.id
                    and self._valid
                )
            )
            await self.stream.open()
            async for event in self.stream:
                if event.interaction.custom_id == "⏮️":
                    await self.session.move_by(-1)
                elif event.interaction.custom_id in ["⏸️", "▶️"]:
                    await self.session.pause()
                    cont = True
                elif event.interaction.custom_id == "⏹️":
                    await self.session.disconnect()
                elif event.interaction.custom_id == "⏭️":
                    await self.session.move_by(1)
                elif event.interaction.custom_id == "🔉":
                    current = await self.session.volumeLevel()
                    await self.session.volume(current - 5)
                    cont = True
                elif event.interaction.custom_id == "🔊":
                    current = await self.session.volumeLevel()
                    await self.session.volume(current + 5)
                    cont = True
                elif event.interaction.custom_id == "🔁":
                    if (await self.session.repeatMode()) != Repeat.ALL:
                        await self.session.repeat(Repeat.ALL)
                    else:
                        await self.session.repeat(Repeat.NONE)
                    cont = True
                elif event.interaction.custom_id == "🔂":
                    if (await self.session.repeatMode()) != Repeat.ONE:
                        await self.session.repeat(Repeat.ONE)
                    else:
                        await self.session.repeat(Repeat.NONE)
                    cont = True

                await event.interaction.create_initial_response(hikari.ResponseType.MESSAGE_UPDATE)
                break
            await self.stream.close()

    async def isValid(self):
        """
        Access the validity property outside of the class.

        Returns
        -------
        bool

        """
        async with self._lock:
            return self._valid

    async def generate(self):
        """
        Generate the initial message.

        This is called at the beginning of playback when the message is first
        initialized for the session, but also after a NowPlayingMessage.close()
        call in EventManager.track_finish(). It generates the new message to be
        used when the queue advances or moves.

        Returns
        -------
        None

        """
        async with self._lock:
            embed = await self.getEmbed()
            rows = await self.getActionRows()
            self._msg = await self.session.bot.rest.create_message(self.session.cid, embed, components=rows)
            self._valid = True
            loop = hikari.internal.aio.get_or_make_loop()
            self.interactionListenerTask = loop.create_task(self.interactionListener())

    async def update(self, event=None):
        """
        Update the message.

        This is can in theory be called anywhere, but it's primarily called in
        EventManager.player_update().

        Parameters
        ----------
        event: typing.Optional[lavasnek_rs.TrackFinish]
            The update event. If not specified, the timeline for the message
            will not be updated.

        Returns
        -------
        None

        """
        async with self._lock:
            if self._valid:
                if event is not None:
                    embed = await self.getEmbed(position=event.state_position)
                else:
                    embed = await self.getEmbed()
                rows = await self.getActionRows()
                await self._msg.edit(embed, components=rows)

    async def close(self):
        """
        Close the message.

        This is called whenever the message needs to be terminated.
        It is primarily called in EventManager.track_finish() though.

        Returns
        -------
        None

        """
        async with self._lock:
            if self._msg.components != []:
                await self._msg.edit(components=[])

            await self.stream.close()
            self.interactionListenerTask.cancel()
            self._msg = None
            self._valid = False
