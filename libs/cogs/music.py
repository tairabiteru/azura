"""Defines music cog. Everything related to playing music."""

from libs.core.conf import conf
from libs.core.permissions import command
from libs.ext.utils import url_is_valid, localnow
from libs.orm.member import Member

from libs.ext.player.player import Player
from libs.ext.player.queue import Repeat
from libs.ext.player.errors import QueueIsEmpty, AlreadyConnectedToChannel, \
 NoVoiceChannel, NoTracksFound, EndOfQueue

import asyncio
import wavelink
import discord
import random
from discord.ext import commands


BUTTONS = {
    "LOWER_VOLUME": '🔉',
    "RAISE_VOLUME": '🔊',
    "LAST": '⏮️',
    "STOP": '⏹️',
    "DISCONNECT": '⏏️',
    "PAUSE_RESUME": '⏯️',
    "NEXT": '⏭️',
    "LOOP_ONE": '🔂',
    "LOOP_ALL": '🔁'
}


def enqArgParse(query):
    """Parse out arguments from enqueueing commands."""
    enqopts = ['fifo', 'lifo', 'interlace', 'random']
    args = {
        'shuffle': False,
        'mode': 'FIFO'
    }

    if "--shuffle" in query:
        args['shuffle'] = True
        query = query.replace("--shuffle", "").strip()

    for opt in enqopts:
        if f"--{opt}" in query:
            args['mode'] = opt.upper()
            query = query.replace(f"--{opt}", "").strip()
    return (query, args)


class Music(commands.Cog, wavelink.WavelinkMixin):
    """Define music cog."""
    def __init__(self, bot):
        """Initialize music cog."""
        self.bot = bot
        self.wavelink = self.bot.wavelink
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Disconnect bot when no one is left in the VC."""
        if not member.bot and after.channel is None:
            members = list([m.id for m in before.channel.members])
            if self.bot.user.id in members and len(members) == 1:
                await self.get_player(member.guild).teardown()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Set up to handle buttons."""
        await self.handle_button(reaction, user)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        """Set up to handle buttons."""
        await self.handle_button(reaction, user)

    async def handle_button(self, reaction, user):
        """Handle buttons."""
        if user.id == self.bot.user.id:
            return

        player = self.get_player(reaction.message.guild)
        try:
            if reaction.message.id != player.plyrmsg.id:
                return
        except AttributeError:
            if player.plyrmsg is None:
                return
            else:
                pass

        member = Member.obtain(user.id)

        if reaction.emoji == BUTTONS['LOWER_VOLUME']:
            volume = player.volume - member.settings.volumeStep
            await player.set_volume(volume)
        if reaction.emoji == BUTTONS['RAISE_VOLUME']:
            volume = player.volume + member.settings.volumeStep
            await player.set_volume(volume)
        if reaction.emoji == BUTTONS['STOP']:
            await player.halt()
            player.queue.clear()
            await player.plyrmsg.channel.send(f"Playback stopped by {user.name}.")
        if reaction.emoji == BUTTONS['DISCONNECT']:
            await player.teardown()
            await player.plyrmsg.channel.send(f"Disconnected by {user.name}.")
        if reaction.emoji == BUTTONS['PAUSE_RESUME']:
            await player.set_pause(not player.is_paused)
            state = "paused" if player.is_paused else "resumed"
            await player.plyrmsg.channel.send(f"Playback {state}.", delete_after=15)
        if reaction.emoji == BUTTONS['NEXT']:
            await player.stop()
        if reaction.emoji == BUTTONS['LAST']:
            player.queue.position -= 2
            await player.stop()
        if reaction.emoji == BUTTONS['LOOP_ONE']:
            player.queue.repeat_mode = Repeat.NONE if player.queue.repeat_mode != Repeat.NONE else Repeat.ONE
            mode = "REPEAT ONE" if player.queue.repeat_mode == Repeat.ONE else "OFF"
            await player.plyrmsg.channel.send(f"Repeat mode set to `{mode}`.", delete_after=15)
        if reaction.emoji == BUTTONS['LOOP_ALL']:
            mode = "REPEAT ALL" if player.queue.repeat_mode == Repeat.ALL else "OFF"
            await player.plyrmsg.channel.send(f"Repeat mode set to `{mode}`.", delete_after=15)

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        """Log when Lavalink node is ready."""
        self.bot.log(f"Connected to node {node.host}:{node.port} as {node.identifier}.")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        """Advance the track, or repeat if mode is set."""
        if payload.player.queue.repeat_mode == Repeat.ONE:
            await payload.player.repeat_track()
        else:
            await payload.player.advance()

    async def start_nodes(self):
        """Initialize Lavalink node."""
        await self.bot.wait_until_ready()

        nodes = {
            "MAIN": {
                "host": conf.wavelink.host,
                "port": conf.wavelink.port,
                "rest_uri": f"http://{conf.wavelink.host}:{conf.wavelink.port}",
                "password": conf.wavelink.password,
                "identifier": conf.name.upper(),
                "region": conf.wavelink.voiceRegion,
            }
        }

        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    @wavelink.WavelinkMixin.listener("on_track_start")
    async def on_track_start(self, node, payload):
        """
        Handle the initialization of the info message and the player message.
        Also start tasks to update the interface periodically.
        """
        try:
            player, track = (payload.player, payload.player.queue.current_track)
            member = Member.obtain(track.requester.id)
            member.update_history(track)
            messages = await track.ctx.channel.history(limit=2).flatten()
            messages = list([message.id for message in messages])
        except (QueueIsEmpty, EndOfQueue):
            return

        try:
            if player.infomsg.id in messages and player.plyrmsg.id in messages:
                await player.infomsg.edit(embed=player.queue.info_embed(self.bot))
                await player.plyrmsg.edit(embed=player.player_embed())
            else:
                await player.infomsg.delete()
                await player.plyrmsg.delete()
                raise AttributeError
        except (AttributeError, discord.errors.NotFound):
            player.infomsg = await track.ctx.send(embed=player.queue.info_embed(self.bot))
            player.plyrmsg = await track.ctx.send(embed=player.player_embed())
            for button in list(BUTTONS.values()):
                await player.plyrmsg.add_reaction(button)
        except QueueIsEmpty:
            return
        player.interface_task = self.bot.loop.create_task(self.interface_updater(track.ctx, track.id))

    def get_player(self, obj):
        """Obtain player either from ctx or guild."""
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    async def interface_updater(self, ctx, id):
        """Task that updates the player interface periodically."""
        player = self.get_player(ctx)
        if player is None:
            return
        try:
            if player.queue.current_track is None:
                return
            while player.queue.current_track.id == id:
                player = self.get_player(ctx)
                try:
                    await player.plyrmsg.edit(embed=player.player_embed())
                except discord.errors.NotFound:
                    # When -np is run, there can be a split second where
                    # player.plyrmsg doesn't exist.
                    await asyncio.sleep(0.1)
                    continue
                await asyncio.sleep(1)
        except QueueIsEmpty:
            await asyncio.sleep(1)
        except EndOfQueue:
            return

    @command(aliases=['join', 'con'])
    async def connect(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Connects the bot to the voice channel you're in.
        You have to be in a voice channel for it to work.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        try:
            player = self.get_player(ctx)
            await player.connect(ctx)
            member = Member.obtain(ctx.author.id)
            await player.set_volume(member.last_volume)
        except AlreadyConnectedToChannel:
            await ctx.send("I'm already connected to a voice channel.")
        except NoVoiceChannel:
            await ctx.send("You must be connected to a voice channel to play music.")

    @command(aliases=["dc"])
    async def disconnect(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Disonnects the bot to the voice channel you're in.
        You have to be in a voice channel for it to work.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)
        await player.teardown()

    @command()
    async def play(self, ctx, *, query):
        """
        Syntax: `{pre}{command_name} <song>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Plays the requested song in the voice channel the bot is connected to.
        If {bot} is not connected, she will attempt to connect to the voice
        channel the command executor is in. If the command executor is not in a
        voice channel, this will fail.

        If a search is specified, {bot} will ask you which of the top five
        results you want. She will provide buttons to press, or you can type in
        the number corresponding to your selection if you want.

        __**Arguments**__
        `<song>` - A search term or URL that leads to the song you want played.
        This can manifest itself as a simple search, "Vince Guaraldi - Skating",
        or it can be entire links: "https://www.youtube.com/watch?v=dQw4w9WgXcQ".
        Links can be for Youtube, Soundcloud, and a myriad of other services.

        __**Example Usage**__
        `{pre}{command_name} Nasko - Break Through`
        `{pre}{command_name} https://www.youtube.com/watch?v=dQw4w9WgXcQ`
        """
        player = self.get_player(ctx)

        query, args = enqArgParse(query)

        if not player.is_connected:
            channel = await player.connect(ctx)
            if not channel:
                return
            member = Member.obtain(ctx.author.id)
            await player.set_volume(member.last_volume)

        member = Member.obtain(ctx.author.id)
        if not url_is_valid(query):
            query = f"ytsearch:{query}"
            tracks = await self.wavelink.get_tracks(query)
            if member.settings.promptOnSearch:
                track = await player.choose_track(ctx, tracks)
                if track is None:
                    return
            else:
                track = tracks[0]
        else:
            track = query
        try:
            await player.add_enqueue_job(ctx, self.wavelink, query.replace("ytsearch:", ""), [track], mode=args['mode'])
        except NoTracksFound:
            return await ctx.send("I couldn't find a track with that name. Try being less specific, or use a link.")

    @command(aliases=['nq', 'enq', 'nqf', 'enqf', 'nqfifo', 'enqfifo', 'enqueue_fifo'])
    async def enqueue(self, ctx, *, playlist_rq):
        """
        Syntax: `{pre}{command_name} <playlist1>|[playlist2]|[playlist3] [--shuffle]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist to be played. By default, it enqueues playlists
        in the order they exist in. Multiple playlists`--shuffle` can be specified to shuffle the
        playlist if desired.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.
        `[--shuffle]` - If specified, shuffles the playlist before enqueueing.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi --shuffle`
        """
        playlist_rq, args = enqArgParse(playlist_rq)
        plentries = []
        member = Member.obtain(ctx.author.id)
        for playlist in playlist_rq.split("|"):
            playlist = member.playlist_exists(playlist.strip())
            if playlist is None:
                return await ctx.send(f"No playlist named `{playlist_rq}` exists.")

            if len(member.playlists[playlist]) == 0:
                return await ctx.send(f"There are no entries in `{playlist}`.")
            plentries += member.playlists[playlist]

        if args['shuffle']:
            random.shuffle(plentries)

        player = self.get_player(ctx)

        if not player.is_connected:
            channel = await player.connect(ctx)
            if not channel:
                return
            await player.set_volume(member.last_volume)
        await player.add_enqueue_job(ctx, self.wavelink, playlist, plentries, mode=args['mode'])

    @command(aliases=['snq', 'senq', 'snqf', 'senqf', 'snqfifo', 'senqfifo'])
    async def shuffle_enqueue(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in shuffled order, using the FIFO enqueueing method.
        This is just a shortcut for `{pre}enqueue <playlist> --shuffle`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --shuffle")

    @command(aliases=['nql', 'enql', 'nqlifo', 'enqlifo'])
    async def enqueue_lifo(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in order, using the LIFO enqueueing method.
        LIFO stands for "Last In, First Out" and enqueues songs placing them
        at the *front* of the queue, before all others. This command is a
        shortcut for `{pre}enqueue <playlist> --lifo`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --lifo")

    @command(aliases=['snql', 'senql', 'snqlifo', 'senqlifo'])
    async def shuffle_enqueue_lifo(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in shuffled order, using the LIFO enqueueing method.
        LIFO stands for "Last In, First Out" and enqueues songs placing them
        at the *front* of the queue, before all others.
        This is just a shortcut for `{pre}enqueue <playlist> --lifo --shuffle`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --shuffle --lifo")

    @command(aliases=['nqr', 'enqr', 'nqrandom', 'enqrandom'])
    async def enqueue_random(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in order, using the RANDOM enqueueing method.
        In RANDOM enqueueing, the positions that songs are enqueued at is
        entirely random. Note that while similar to shuffling a playlist, it is
        not the same. Rather than placing songs strictly at the front (LIFO) or
        or the back (FIFO), or interweaving them (INTERLACE), songs have their
        positions determined entirely randomly. This command is a shortcut for
        `{pre}enqueue <playlist> --random`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --lifo")

    @command(aliases=['snqr', 'senqr', 'snqrandom', 'senqrandom'])
    async def shuffle_enqueue_random(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in shuffled order, using the RANDOM enqueueing method.
        In RANDOM enqueueing, the positions that songs are enqueued at is
        entirely random. Note that while similar to shuffling a playlist, it is
        not the same. Rather than placing songs strictly at the front (LIFO) or
        or the back (FIFO), or interweaving them (INTERLACE), songs have their
        positions determined entirely randomly. This command is a shortcut for
        `{pre}enqueue <playlist> --random --shuffle`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --shuffle --random")

    @command(aliases=['nqi', 'enqi', 'nqinterlace', 'enqinterlace'])
    async def enqueue_interlace(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in order, using the INTERLACE enqueueing method.
        In INTERLACE enqueueing, songs are enqueued every `n` positions, where
        `n` is the number of unique song requesters in the current queue, plus 1.
        For example, if two people have songs in the queue, one song from your
        playlist will be enqueued in every third position.
        This command is a shortcut for `{pre}enqueue <playlist> --interlace`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --interlace")

    @command(aliases=['snqi', 'senqi', 'snqinterlace', 'senqinterlace'])
    async def shuffle_enqueue_interlace(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist in shuffled order, using the INTERLACE enqueueing method.
        In INTERLACE enqueueing, songs are enqueued every `n` positions, where
        `n` is the number of unique song requesters in the current queue, plus 1.
        For example, if two people have songs in the queue, one song from your
        playlist will be enqueued in every third position.
        This command is a shortcut for `{pre}enqueue <playlist> --interlace --shuffle`.

        __**Arguments**__
        `<playlist>` - The name of the playlist to be enqueued. Only playlists
        you own can be enqueued by you. To see your playlists, you can run
        {pre}show_playlist. To define them, see the commands in the Playlisting
        cog.

        __**Example Usage**__
        `{pre}{command_name} Electronic`
        `{pre}{command_name} Lo-Fi`
        """
        enqueue = self.bot.get_command('enqueue')
        await ctx.invoke(enqueue, playlist_rq=f"{playlist} --shuffle --interlace")

    @command(aliases=['dq', 'deq', 'cleanqueue', 'queueclean', 'qclean', 'cleanq'])
    async def dequeue(self, ctx, member: discord.Member = None):
        """
        Syntax: `{pre}{command_name} [@Member]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Removes songs from the queue. How it does this depends on the arguments
        passed.

        __**Arguments**__
        `[@Member]` - The optional member argument. If specified, any songs
        requested by the specified member will be removed from the queue.
        If not specified, all songs requested by members who are not in the same
        voice channel as the bot at the time the command is run will be removed.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} @Taira`
        """
        player = self.get_player(ctx)
        await player.add_enqueue_job(ctx, self.wavelink, member=member, mode='DEQ')

    @command()
    async def pause(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Pauses playback. Unpause with `{pre}unpause`.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)

        if player.is_paused:
            return await ctx.send("Playback is already paused.")

        await player.set_pause(True)

    @command()
    async def unpause(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Unpauses paused playback.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)

        if not player.is_paused:
            return await ctx.send("Playback is already unpaused.")

        await player.set_pause(False)

    @command()
    async def stop(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Stops playback and empties the queue. It does not disconnect the bot though.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)
        player.queue.clear()
        await player.stop()
        await ctx.send("Playback terminated, queue emptied.")

    @command(aliases=["next"])
    async def skip(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Skips the present song and moves to the next in queue. If nothing else
        is in the queue, playback is halted.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)

        try:
            _ = player.queue.next_tracks
        except QueueIsEmpty:
            return await ctx.send("There are no more tracks in the queue.")

        await player.stop()

    @command(aliases=['previous', 'prev'])
    async def last(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Moves back to the previous song in the queue.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)

        if not player.queue.past_tracks:
            return await ctx.send("There are no tracks before this one.")

        player.queue.position -= 2
        await player.stop()

    @command()
    async def shuffle(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Shuffles the songs currently in the queue.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)
        if player.queue.empty:
            return await ctx.send("The queue is empty.")

        player.queue.shuffle()
        return await ctx.send("Queue shuffled.")

    @command()
    async def repeat(self, ctx, mode="one"):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Sets the repeat mode.

        __**Arguments**__
        `[mode]` - The repeat mode. Must be one of `none`, `one`, or `all`.
        If not specified, it defaults to `one`.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        mode = mode.lower()
        if mode not in ["none", "one", "all"]:
            return await ctx.send(f"Invalid mode `{mode}` Mode must be one of `none`, `one`, or `all`.")

        player = self.get_player(ctx)
        player.queue.set_repeat_mode(mode)
        await ctx.send(f"Repeat set to  `repeat {mode}`.")

    @command(aliases=['q'])
    async def queue(self, ctx, number=10):
        """
        Syntax: `{pre}{command_name} [number]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Displays the queue, with the specified number of entries. If not
        specified, it shows the next 10 entries.

        __**Arguments**__
        `[number]` - The number of entries to show.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} 15`
        """
        player = self.get_player(ctx)

        try:
            status = player.queue.current_track
            status = "good"
        except QueueIsEmpty:
            status = "empty"
        except EndOfQueue:
            status = "end"

        if status == "empty":
            return await ctx.send("The queue is empty.")
        if status == "end":
            return await ctx.send("The queue has reached the end.")


        embed = discord.Embed(
            title="Queue",
            description=f"Showing up to next {number} tracks",
            colour=ctx.author.colour,
            timestamp=localnow()
        )
        embed.set_author(name="Query Results")
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar_url)
        embed.add_field(
            name="Currently playing",
            value=getattr(player.queue.current_track, "title", "No tracks currently playing."),
            inline=False
        )
        upcoming = player.queue.next_tracks
        if upcoming:
            embed.add_field(
                name="Next up",
                value="\n".join(t.title for t in upcoming[:number]),
                inline=False
            )

        await ctx.send(embed=embed)

    @command(aliases=['np', 'current'])
    async def now_playing(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Re-renders the now playing messages. This is useful if it has gotten
        buried in other commands.

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        player = self.get_player(ctx)

        if not player.is_connected or not player.is_playing:
            return await ctx.send("I'm not playing anything.")

        try:
            await player.infomsg.delete()
            await player.plyrmsg.delete()
            await player.enqmsg.delete()
        except AttributeError:
            pass
        player.enqmsg = None
        player.infomsg = await ctx.send(embed=player.queue.info_embed(ctx.bot))
        player.plyrmsg = await ctx.send(embed=player.player_embed())

        for button in list(BUTTONS.values()):
            await player.plyrmsg.add_reaction(button)

    @command(aliases=['vol'])
    async def volume(self, ctx, volume):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Sets the volume.

        The volume setting can either be a whole integer between 0 and 1000, or
        a whole number preprended with `+` or `-`. When a number is specified, the
        volume will simply be set to that number. If prepended with a `+` or `-`
        however, the number specified after will be added or subtracted from the
        current volume. For example, if the volume is `100` and `{pre}volume -10`
        is run, the volume will have `10` subtracted from it. `100 - 10 = 90`, and
        so the new volume would be `90`.

        __**Arguments**__
        `<volume>` - The volume setting. Must be either a whole number between 0
        and 1000, or a whole number preprended with `+` or `-`.

        __**Example Usage**__
        `{pre}{command_name} 10`
        `{pre}{command_name} +20`
        `{pre}{command_name} -5`
        """
        player = self.get_player(ctx)
        if not volume.isdigit():
            vol = volume.replace(" ", "")
            if vol.startswith("+") and vol.replace("+", "").isdigit():
                volume = player.volume + int(vol.replace("+", ""))
            elif vol.startswith("-") and vol.replace("-", "").isdigit():
                volume = player.volume - int(vol.replace("-", ""))
            else:
                return await ctx.send(f"Invalid volume setting `{volume}`. Volume must be a whole number between 0 and 1000.")
        else:
            volume = int(volume)

        if volume > 1000 or volume < 0:
            return await ctx.send(f"Volume setting of `{volume}` outside of range. Volume must be between 0 and 1000.")

        member = Member.obtain(ctx.author.id)
        member.last_volume = volume
        member.save()

        await player.set_volume(volume)
        return await ctx.send(f"Volume set to {volume}%")

    @command(aliases=['xmas'])
    async def christmas(self, ctx):
        """
        Syntax: `{pre}{command_name}`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueue a special shuffled playlist of holiday music. This command will
        only succeed in December, so use it while you can!

        __**Arguments**__
        This command takes no arguments.

        __**Example Usage**__
        `{pre}{command_name}`
        """
        if localnow().strftime("%m") != "12":
            return await ctx.send("It's not even december.")

        player = self.get_player(ctx)

        if not player.is_connected:
            channel = await player.connect(ctx)
            if not channel:
                return
            member = Member.obtain(ctx.author.id)
            await player.set_volume(member.last_volume)

        admin = Member.obtain(conf.ownerID)
        plentries = admin.playlists["Christmas"]
        random.shuffle(plentries)
        await player.add_enqueue_job(ctx, self.wavelink, "Christmas Music", plentries)


def setup(bot):
    """Setup music cog."""
    bot.add_cog(Music(bot))
