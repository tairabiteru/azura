from ..mvc.discord.models import User
from ..mvc.music.models import Playlist, PlaylistEntry
from ..ext.ctx import ValidationMenu
import azura.keikou as keikou


playlist_plugin = keikou.Plugin("playlist")
playlist_plugin.description = "Commands related to playlist construction and manipulation."


@playlist_plugin.command()
@keikou.command("add", "Commands that add something.")
@keikou.implements(keikou.SlashCommandGroup)
async def add(ctx):
    pass


@add.child()
@keikou.option("public", "If a playlist is public, it can be enqueued by others, but not modified.", type=bool, default=True)
@keikou.option("description", "A description for the playlist.", type=str, default="No description provided.")
@keikou.option("name","The name of the playlist.", type=str)
@keikou.command("playlist", "Add a new playlist.")
@keikou.implements(keikou.SlashSubCommand)
async def add_playlist(ctx):
    if len(ctx.options.name) > 256:
        return await ctx.respond("Playlist names cannot be longer than 256 characters.")

    owner, _ = await User.objects.aget_or_create(id=ctx.author.id)
    playlist, created = await Playlist.objects.aget_or_create(owner=owner, name=ctx.options.name)
    if not created:
        return await ctx.respond(f"You already have a playlist named `{ctx.options.name}`.")
    
    playlist.description = ctx.options.description
    playlist.is_public = ctx.options.public
    await playlist.asave()
    owner.selected_playlist = playlist
    await owner.asave()
    return await ctx.respond(f"`{playlist.name}` has been created. It is now the selected playlist.", embed=(await playlist.get_embed()))


@add.child()
@keikou.option("end", "The spot in the song where playback should end. If not specified, it will stop at the end.", type=str, default=None)
@keikou.option("start", "The spot in the song where playback should start. If not specified, it will start at the beginning.", type=str, default=None)
@keikou.option("title", "The title of the song. If not specified, it will be extrapolated from the source.", type=str, default=None)
@keikou.option("source", "The source for the song. See the help page about sources for more details.", type=str)
@keikou.option("playlist", "The name of the playlist to add the song to. Uses the selected playlist if not specified.", type=str, default=None)
@keikou.command("song", "Add a song to a playlist.")
@keikou.implements(keikou.SlashSubCommand)
async def add_song(ctx):
    owner, _ = await User.objects.select_related("selected_playlist").aget_or_create(id=ctx.author.id)
    if ctx.options.playlist is None:
        if owner.selected_playlist is None:
            return await ctx.respond("You do not have a selected playlist. You must specify which playlist to add a song to.")
        playlist = owner.selected_playlist
    else:
        try:
            playlist = await Playlist.objects.aget(name=ctx.options.playlist, owner=owner)
        except Playlist.DoesNotExist:
            return await ctx.respond(f"A playlist named `{ctx.options.playlist}` does not exist.")
    
    try:
        start = PlaylistEntry.validate_timedelta(ctx.options.start)
        end = PlaylistEntry.validate_timedelta(ctx.options.end)
    except ValueError as e:
        return await ctx.respond(str(e))
    
    if ctx.options.title is None:
        track = await ctx.bot.hanabi.load_or_search_tracks(ctx.options.source)
        if track is None:
            return await ctx.respond("The source provided did not return any tracks.")
        elif isinstance(track, list):
            track = track[0]
        title = track.info.title
    else:
        title = ctx.options.title
    
    try:
        await PlaylistEntry.objects.aget(playlist=playlist, title=title)
        return await ctx.respond(f"An entry with the title `{ctx.options.title}` already exists in the playlist `{playlist.name}`.")
    except PlaylistEntry.DoesNotExist:
        pass
    
    entry = PlaylistEntry(playlist=playlist, title=title)
    entry.source = ctx.options.source
    entry.index = await playlist.get_next_index()
    entry.start = start
    entry.end = end
    await entry.asave()
    return await ctx.respond(f"Added the following entry to `{playlist.name}`:", embed=(await entry.get_embed()))
    

@playlist_plugin.command()
@keikou.command("show", "Commands that show something.")
@keikou.implements(keikou.SlashCommandGroup)
async def show(ctx):
    pass


@show.child()
@keikou.option("name", "The name of the playlist to show. If not specified, all playlists will be shown.", type=str, default=None)
@keikou.command("playlist", "Show a playlist, or all of your playlists.")
@keikou.implements(keikou.SlashSubCommand)
async def show_playlist(ctx):
    owner, _ = await User.objects.aget_or_create(id=ctx.author.id)

    if ctx.options.name is not None:
        try:
            playlist = await Playlist.objects.aget(owner=owner, name=ctx.options.name)
            return await ctx.respond((await playlist.get_embed()))
        except Playlist.DoesNotExist:
            return await ctx.respond(f"You don't have a playlist named `{ctx.options.name}`.")
    
    playlists = await owner.get_playlists()
    if not playlists:
        return await ctx.respond("You don't have any playlists.")
    
    content = ""
    for playlist in playlists:
        content += f"• {playlist.name} - {playlist.description}\n"
    return await ctx.respond(f"```{content}```")


@playlist_plugin.command()
@keikou.command("delete", "Commands that delete something.")
@keikou.implements(keikou.SlashCommandGroup)
async def delete(ctx):
    pass


@delete.child()
@keikou.option("name", "The name of the playlist to be deleted.")
@keikou.command("playlist", "Delete a playlist. THIS IS IRREVERSIBLE.")
@keikou.implements(keikou.SlashSubCommand)
async def delete_playlist(ctx):
    owner, _ = await User.objects.aget_or_create(id=ctx.author.id)
    try:
        playlist = await Playlist.objects.aget(owner=owner, name=ctx.options.name)
    except Playlist.DoesNotExist:
        return await ctx.respond(f"You do not have a playlist named `{ctx.options.name}`.")
    
    msg = f"You are about to delete the playlist `{playlist.name}`. This action is **__IRREVERSIBLE__**!"
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    await menu.start((await resp.message()))
    await menu.wait_for_input()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])
    
    await playlist.adelete()
    await ctx.edit_last_response(f"`{playlist.name}` was deleted.", components=[])





def load(bot):
    bot.add_plugin(playlist_plugin)


def unload(bot):
    bot.remove_plugin(playlist_plugin)