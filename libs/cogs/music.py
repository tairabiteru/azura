from libs.core.conf import conf
from libs.core.permissions import command
from libs.core.log import logprint
from libs.ext.utils import url_is_valid, localnow
from libs.orm.member import Member

from libs.ext.player.player import Player
from libs.ext.player.queue import Repeat
from libs.ext.player.errors import QueueIsEmpty, AlreadyConnectedToChannel, NoVoiceChannel

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


class Music(commands.Cog, wavelink.WavelinkMixin):
    def __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and after.channel is None:
            members = list([m.id for m in before.channel.members])
            if self.bot.user.id in members and len(members) == 1:
                await self.get_player(member.guild).teardown()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        await self.handle_button(reaction, user)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        await self.handle_button(reaction, user)

    async def handle_button(self, reaction, user):
        if user.id == self.bot.user.id:
            return

        player = self.get_player(reaction.message.guild)
        try:
            if reaction.message.id != player.plyrmsg.id:
                return
        except AttributeError:
            pass

        member = Member.obtain(user.id)

        if reaction.emoji == BUTTONS['LOWER_VOLUME']:
            volume = player.volume - member.settings.volumeStep
            await player.set_volume(volume)
        if reaction.emoji == BUTTONS['RAISE_VOLUME']:
            volume = player.volume + member.settings.volumeStep
            await player.set_volume(volume)
        if reaction.emoji == BUTTONS['STOP']:
            if player.enqueueing:
                player.stop_signal = True
            player.queue.clear()
            await player.stop()
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
            player.queue.repeat_mode = Repeat.NONE if player.queue.repeat_mode != Repeat.NONE else Repeat.ALL
            mode = "REPEAT ALL" if player.queue.repeat_mode == Repeat.ALL else "OFF"
            await player.plyrmsg.channel.send(f"Repeat mode set to `{mode}`.", delete_after=15)

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        logprint(f"Connected to node {node.host}:{node.port} as {node.identifier}.")

    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        if payload.player.queue.repeat_mode == Repeat.ONE:
            await payload.player.repeat_track()
        else:
            await payload.player.advance()

    async def start_nodes(self):
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
        player, track = (payload.player, payload.player.queue.current_track)
        member = Member.obtain(track.requester.id)
        member.update_history(track)
        messages = await track.ctx.channel.history(limit=2).flatten()
        messages = list([message.id for message in messages])

        try:
            if player.infomsg.id in messages and player.plyrmsg.id in messages:
                await player.infomsg.edit(embed=player.queue.info_embed(self.bot))
                await player.plyrmsg.edit(embed=player.player_embed())
            else:
                await player.infomsg.delete()
                await player.plyrmsg.delete()
                raise AttributeError
        except (AttributeError, discord.errors.NotFound) as e:
            player.infomsg = await track.ctx.send(embed=player.queue.info_embed(self.bot))
            player.plyrmsg = await track.ctx.send(embed=player.player_embed())
            for button in list(BUTTONS.values()):
                await player.plyrmsg.add_reaction(button)
        player.interface_task = self.bot.loop.create_task(self.interface_updater(track.ctx, track.id))

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)

    async def interface_updater(self, ctx, id):
        player = self.get_player(ctx)
        if player is None:
            return
        try:
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

        if not player.is_connected:
            channel = await player.connect(ctx)
            if not channel:
                return
            member = Member.obtain(ctx.author.id)
            await player.set_volume(member.last_volume)

        if not url_is_valid(query):
            query = f"ytsearch:{query}"
        try:
            tracks = await self.wavelink.get_tracks(query)
            await player.add_tracks(ctx, tracks)
        except NoTracksFound:
            return await ctx.send("I couldn't find a track with that name. Try being less specific, or use a link.")

    @command(aliases=['nq', 'enq'])
    async def enqueue(self, ctx, *, playlist_rq):
        """
        Syntax: `{pre}{command_name} <playlist> [--shuffle]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist to be played. By default, it enqueues playlists
        in the order they exist in. `--shuffle` can be specified to shuffle the
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
        member = Member.obtain(ctx.author.id)
        shuffle = False
        if playlist_rq.endswith("--shuffle"):
            shuffle = True
            playlist_rq = playlist_rq.replace("--shuffle", "").strip()

        playlist = member.playlist_exists(playlist_rq)
        if not playlist:
            return await ctx.send(f"No playlist named `{playlist_rq}` exists.")

        if len(member.playlists[playlist]) == 0:
            return await ctx.send(f"There are no entries in `{playlist}`.")

        player = self.get_player(ctx)

        if not player.is_connected:
            channel = await player.connect(ctx)
            if not channel:
                return
            member = Member.obtain(ctx.author.id)
            await player.set_volume(member.last_volume)

        plentries = member.playlists[playlist]
        if shuffle:
            random.shuffle(plentries)
        enqueued, failures = await player.add_playlist(ctx, self.wavelink, plentries)
        msg = f"Enqueued {len(enqueued)} song(s)"
        if failures:
            msg += f" with {len(failures)} failure(s):```CSS\n"
            for failure in failures:
                msg += f"{failure.generator} - {failure.custom_title}\n"
            msg += "```\nThis is usually because the videos have been removed from Youtube."
            await ctx.send(msg)
        else:
            await ctx.send(msg + ".", delete_after=30)

    @command(aliases=['rnq', 'renq'])
    async def random_enqueue(self, ctx, *, playlist):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Enqueues a playlist to be played in random order. This is just a
        shortcut for `{pre}enqueue <playlist> --shuffle`.

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
        if player.enqueueing:
            player.stop_signal = True
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

        if player.queue.empty:
            return await ctx.send("The queue is empty.")

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
        except AttributeError:
            pass
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
        enqueued, failures = await player.add_playlist(ctx, self.wavelink, plentries)
        msg = f"Enqueued {len(enqueued)} song(s)"
        if failures:
            msg += f" with {len(failures)} failure(s):```CSS\n"
            for failure in failures:
                msg += f"{failure.generator} - {failure.custom_title}\n"
            msg += "```"
        else:
            msg += "."
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(Music(bot))
