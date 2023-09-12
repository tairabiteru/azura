from ..core.conf.loader import conf
from ..hanabi.objects import EnqueueMode
from ..ext.utils import get_thanksgiving_of
import azura.keikou as keikou
import azura.hanabi as hanabi

import hikari
import re
import zoneinfo


music = keikou.Plugin("music")
music.description = f"Commands related to the audio playback of {conf.name}."


@music.command()
@keikou.option("bot", "Connect the bot of your choosing.", default=None)
@keikou.command("connect", f"Connect {conf.name} to the voice channel you're in.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=True)
async def connect(ctx, session):
    await ctx.respond("Received...", delete_after=1)


@music.command()
@keikou.command("disconnect", f"Disconnect {conf.name} from a voice channel.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def disconnect(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.disconnect()
    

@music.command()
@keikou.option("position", "The position to place the track in. For more information, view the help page on Queue Position.", type=int, default=None)
@keikou.option("title", "The title of the track to play, or a link to the track.")
@keikou.command("play", "Play a song.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=True)
async def play(ctx, session):
    await session.play_cmd(ctx.options.title, ctx.author.id, position=ctx.options.position)
    await ctx.respond("Acknowledged", delete_after=1)


@music.command()
@keikou.option("by", "The number to skip by.", type=int, default=None)
@keikou.option("to", "The position to skip to.", type=int, default=None)
@keikou.command("skip", "Skip by a number of tracks, or to a track.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def skip(ctx, session):
    if ctx.options.by and ctx.options.to:
        return await ctx.respond("You cannot specify both the `by` and `to` options. You must only use one or the other.", delete_after=30)
    elif not ctx.options.by and not ctx.options.to:
        by, to = 1, None
    else:
        by, to = ctx.options.by, ctx.options.to
    await ctx.respond("Received...", delete_after=1)
    await session.skip(by=by, to=to)
    


@music.command()
@keikou.option("mode", "The repeat mode to set.", choices=["NONE", "ONE", "ALL"])
@keikou.command("repeat", "Set the repeat mode for the queue.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def repeat(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    mode = getattr(hanabi.objects.RepeatMode, ctx.options.mode)
    await session.set_repeat_mode(mode)


@music.command()
@keikou.command("pause", "Pause the current track.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def pause(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.pause_cmd(True)


@music.command()
@keikou.command("resume", "Resume the current track.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def resume(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.pause_cmd(False)


@music.command()
@keikou.command("unpause", "Unpause the current track.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def unpause(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.pause_cmd(False)


@music.command()
@keikou.option("setting", "The setting to use. Ex: 25, -10, +20.")
@keikou.command("volume", "Set the volume.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def volume(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.volume_cmd(ctx.author.id, ctx.options.setting)


@music.command()
@keikou.option("owner", "The owner of the playlist. Defaults to you.", default=None, type=hikari.User)
@keikou.option("mode", "The mode in which to enqueue the playlist. Defaults to FIFO.", default="FIFO", choices=['FIFO', 'LIFO', 'RANDOM', 'INTERLACE'])
@keikou.option("shuffle", "Shuffle the playlist before enqueuing. Defaults to unshuffled.", default='No', choices=['No', 'Yes'])
@keikou.option("name", "The name of the playlist to enqueue.")
@keikou.command("enqueue", "Enqueue a playlist.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=True)
async def enqueue(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    owner = ctx.author.id if ctx.options.owner is None else ctx.options.owner.id
    shuffle = True if ctx.options.shuffle == "Yes" else False
    mode = EnqueueMode(ctx.options.mode)
    bypass_owner = ctx.invoked_with == "christmas"
    await session.enqueue_cmd(ctx.options.name, owner, ctx.author.id, shuffle, mode, bypass_owner=bypass_owner)


@music.command()
@keikou.command("queue", "Show the current queue.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def queue(ctx, session):
    await ctx.respond("Received...", delete_after=1)
    await session.display_queue(amount=20)


@music.command()
@keikou.command("stats", "View stats related to the Lavalink connection.")
@keikou.implements(keikou.SlashCommand)
async def stats(ctx):
    return await ctx.respond(ctx.bot.hanabi.get_stats_embed())


@music.command()
@keikou.command("christmas", "Enqueue the holiday playlist. This can only be done after US Thanksgiving.")
@keikou.implements(keikou.SlashCommand)
async def christmas(ctx):
    """
    Define the Christmas command.
    
    This command basically just shuffles my own Christmas playlist.
    It uses a lot of hard coded stuff, but...come at me.
    """
    now = ctx.bot.localnow()
    day_after = get_thanksgiving_of(now.year)
    day_after = day_after.replace(tzinfo=zoneinfo.ZoneInfo(ctx.bot.conf.timezone))
    if now < day_after:
        return await ctx.respond("It's not even after Thanksgiving yet, jeez.")

    ctx.options._options['name'] = "Christmas"
    ctx.options._options['owner'] = ctx.bot.cache.get_user(ctx.bot.conf.owner_id)
    ctx.options._options['mode'] = "FIFO"
    ctx.options._options['shuffle'] = True
    await enqueue(ctx)


@music.command()
@keikou.option("requester", "The person whose tracks should be dequeued.", default=None, type=hikari.User)
@keikou.option("positions", "A list of positions to be dequeued, comma separated.", default=None, type=str)
@keikou.command("dequeue", "Dequeue tracks from the queue by position or by requester.")
@keikou.implements(keikou.SlashCommand)
@hanabi.require_voice(auto_connect=False)
async def dequeue(ctx, session):
    if ctx.options.positions is not None:
        if not re.fullmatch("(\d,? ?)+", ctx.options.positions):
            return await ctx.respond(f"Invalid positions: `{ctx.options.positions}`. Positions must be comma separated whole numbers.")
        positions = ctx.options.positions.replace(" ", "")
        positions = list(map(int, positions.split(",")))
        
    else:
        positions = None
    
    if ctx.options.requester is not None:
        requester = ctx.options.requester.id
    else:
        requester = None
    
    if positions is None and requester is None:
        return await ctx.respond("You must specify either positions or a requester.")
    if positions is not None and requester is not None:
        return await ctx.respond("You cannot specify positions and a requester at the same time.")

    await ctx.respond("Received...", delete_after=1)
    await session.dequeue_cmd(positions=positions, requester=requester)


def load(bot):
    bot.add_plugin(music)


def unload(bot):
    bot.remove_plugin(music)