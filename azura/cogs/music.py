"""
Define the music plugin.

This plugin represents the core of Azura's functionality.
"""

from core.conf import conf
from ext.ctx import respond_with_timeout
import orm.models as models
from koe.objects import EnqueueMenu
from koe.enums import RepeatMode
from ext.utils import getThanksgivingOf

import datetime
import hikari
import keikou
import koe


music = keikou.Plugin("music")
music.description = "Commands pertaining to the playback of music."


@music.command()
@keikou.option("bot", "Allows you to specify which bot you'd like to connect. Only available to admins.", choices=[conf.parent.name] + [child.name for child in conf.children], default=None)
@keikou.command("connect", f"Connect {conf.parent.name} or one of her children to the channel you're in.")
@keikou.implements(keikou.SlashCommand)
async def connect(ctx):
    if ctx.options.bot not in [None, conf.parent.name] and ctx.author.id != conf.owner_id:
        return await ctx.respond("Only my maintainer is allowed to specify the connecting bot.")

    args = await ctx.bot.koe.get_args(ctx)
    if args[1] is None:
        return await ctx.respond("You must be connected to a voice channel to use this command.")

    try:
        session = await ctx.bot.koe.create_session(*args, bot_name=ctx.options.bot)
        return await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.ExistingSession:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        if isinstance(session, koe.LocalSession):
            return await ctx.respond("I'm already connected to the voice channel you're in.")
        return await ctx.respond(f"{session.child_name.capitalize()} is already connected to the voice channel you're in.")
    except koe.AllSessionsBusy:
        return await ctx.respond("My children and I are all busy.")


@music.command()
@keikou.command("disconnect", f"Disconnect {conf.parent.name} or one of her children from the channel you're in.")
@keikou.implements(keikou.SlashCommand)
async def disconnect(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    if args[1] is None:
        return await ctx.respond("You must be connected to a voice channel to use this command.")
    try:
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
        await ctx.bot.koe.destroy_session(args[1], must_exist=True)
    except koe.NoExistingSession:
        await ctx.respond("I'm not connected to the voice channel you're in.")


@music.command()
@keikou.option("position", "The position to place the song at. For more information, view the help page for queue position.", type=int, default=-1)
@keikou.option("song", "The name of the song to play, or a link to the song.")
@keikou.command("play", "Play a song.")
@keikou.implements(keikou.SlashCommand)
async def play(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        await connect(ctx)
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])

    await session.play(ctx.author, ctx.options.song, position=ctx.options.position)


@music.command()
@keikou.option("to", "The track number to skip to.", type=int, default=None)
@keikou.option("by", "The number of tracks to skip by.", type=int, default=None)
@keikou.command("skip", "Skip to or by a number of tracks. Defaults to skipping by 1.")
@keikou.implements(keikou.SlashCommand)
async def skip(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    session = await ctx.bot.koe.get_session_from_voice_id(args[1])

    if ctx.options.to is not None and ctx.options.by is not None:
        return await ctx.respond("You must specify either the `to` option or the `by` option, but not both.")

    if ctx.options.by == 0:
        return await ctx.respond("You want me to skip by 0 songs...let's think about why that doesn't work.")

    to = ctx.options.to
    by = ctx.options.by

    if to is not None:
        to -= 1

    if by is None and to is None:
        by = 1

    await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    await session.skip(ctx.author, by=by, to=to)


@music.command()
@keikou.command("queue", "Show the current queue.")
@keikou.implements(keikou.SlashCommand)
async def queue(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    if args[1] is None:
        return await ctx.respond("You must be connected to a voice channel to use this command.")

    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        return await ctx.respond("I'm not connected to a voice channel you're in.")
    
    await session.display_queue(amount=20)


@music.command()
@keikou.option("setting", "The value to set the volume to.", type=int)
@keikou.command("volume", "Set the volume.")
@keikou.implements(keikou.SlashCommand)
async def volume(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        return await ctx.respond("I'm not connected to a voice channel you can set the volume for.")

    await session.set_volume(ctx.author, setting=ctx.options.setting)


@music.command()
@keikou.command("pause", "Pause or unpause the player.")
@keikou.implements(keikou.SlashCommand)
async def pause(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        return await ctx.respond("I'm not connected to a voice channel you're in.")

    await session.pause()


@music.command()
@keikou.command("now", "Now playing command.")
@keikou.implements(keikou.SlashCommandGroup)
async def now(ctx):
    pass


@now.child()
@keikou.command("playing", f"Resends the message {conf.parent.name} first sends when starting playback.")
@keikou.implements(keikou.SlashSubCommand)
async def playing(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        return await ctx.respond("I'm not connected to a voice channel you're in.")

    await session.display_playback()


@music.command()
@keikou.command("repeat", "Repeat mode command.")
@keikou.implements(keikou.SlashCommandGroup)
async def repeat(ctx):
    pass


@repeat.child()
@keikou.option("mode", "The repeat mode to set.", choices=[mode.value for mode in RepeatMode])
@keikou.command("mode", "Sets the repeat mode.")
@keikou.implements(keikou.SlashSubCommand)
async def mode(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        return await ctx.respond("I'm not connected to a voice channel you're in.")

    for mode in RepeatMode:
        if mode.value == ctx.options.mode:
            break
    await session.set_repeat_mode(mode)


@music.command()
@keikou.option("user", "The user whose playlist you want to enqueue. Not needed if you're enqueueing your own.", type=hikari.User, default=None)
@keikou.option("mode", "The mode to use when inserting songs into the current queue. Defaults to FIFO.", choices=["FIFO", "LIFO", "RANDOM", "INTERLACE"], default="FIFO")
@keikou.option("shuffle", "Whether or not the playlist should be shuffled before enqueueing. Defaults to False.", choices=["True", "False"], default="False")
@keikou.option("name", "The name of the playlist to be enqueued.", type=str, default=None)
@keikou.command("enqueue", "Enqueue playlists.")
@keikou.implements(keikou.SlashCommand)
async def enqueue(ctx):
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        await connect(ctx)
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
    
    shuffle = True if ctx.options.shuffle == "True" else False

    if ctx.options.name is None:
        user = ctx.options.user if ctx.options.user else ctx.author
        user = await models.User.get_or_create(user)
        if user.hikari_user != ctx.author:
            playlists = await user.playlists.all().filter(is_public=True)
        else:
            playlists = await user.playlists.all()

        if not playlists:
            if user.hikari_user == ctx.author:
                return await ctx.respond("You don't have any playlists.")
            else:
                return await ctx.respond(f"{user.hikari_user.username} does not have any public playlists defined.")
        
        menu = EnqueueMenu(playlists)
        resp = await ctx.respond("Select a playlist:", components=menu.build())
        await menu.start((await resp.message()))
        await menu.submitted.wait()

        if not menu.proceed:
            return await ctx.edit_last_response("Cancelled.")

        if menu.selection is not None:
            shuffle = "on" if menu.shuffle is True else "off"
            await ctx.edit_last_response(f"Enqueueing `{menu.selection}` with shuffle `{shuffle}`, in `{menu.mode}` mode.", components=[])
            await session.enqueue(
                ctx.author,
                menu.selection,
                shuffle=menu.shuffle,
                mode=menu.mode,
                user=user.hikari_user
            )
            
        else:
            await ctx.edit_last_response("Selection timed out.")
    else:
        await session.enqueue(
            ctx.author,
            ctx.options.name,
            shuffle=shuffle,
            mode=ctx.options.mode,
            user=ctx.options.user
        )

@music.command()
@keikou.command("christmas", "Enqueue the holiday playlist. This can only be done after Thanksgiving.")
@keikou.implements(keikou.SlashCommand)
async def christmas(ctx):
    day_after = getThanksgivingOf(datetime.datetime.now().year) + datetime.timedelta(days=1)
    if datetime.datetime.now() < day_after:
        return await ctx.respond("It's not even after Thanksgiving yet.")
    
    args = await ctx.bot.koe.get_args(ctx)
    try:
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])
        await respond_with_timeout(ctx, "Acknowledged.", timeout=10)
    except koe.NoExistingSession:
        await connect(ctx)
        session = await ctx.bot.koe.get_session_from_voice_id(args[1])

    await session.enqueue(
        ctx.author,
        "Christmas",
        shuffle=True,
        mode="FIFO",
        user=246083582886412290
    )


def load(bot):
    bot.add_plugin(music)


def unload(bot):
    bot.remove_plugin(music)
