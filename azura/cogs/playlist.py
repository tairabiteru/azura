"""
Define the playlist plugin.

This plugin represents commands which allow for the construction of playlists.
"""

from ext.ctx import ValidationMenu
import orm.models as models

import keikou


playlist = keikou.Plugin("playlist")
playlist.description = "Commands pertaining to playlist construction."


@playlist.command()
@keikou.command("add", "Commands that add to something.")
@keikou.implements(keikou.SlashCommandGroup)
async def add(ctx):
    pass


@add.child()
@keikou.option("public", "If a playlist is public, it can be listened to by others, but not modified.", type=bool, default=True)
@keikou.option("description", "A description for the playlist.", type=str, default="No description provided.")
@keikou.option("name", "The name of the playlist.", type=str)
@keikou.command("playlist", "Add a new playlist.")
@keikou.implements(keikou.SlashSubCommand)
async def add_playlist(ctx):
    if len(ctx.options.name) > 256:
        return await ctx.respond("Playlist names cannot be longer than 256 characters.")

    existing = await models.Playlist.get_or_none(owner=ctx.author, name=ctx.options.name)
    if existing:
        return await ctx.respond(f"You already have a playlist named `{ctx.options.name}`.")

    description = "No description provided" if ctx.options.description is None else ctx.options.description 
    public = False if ctx.options.public is None else ctx.options.public

    playlist = await models.Playlist.create(
        owner=ctx.author,
        name=ctx.options.name,
        description=description,
        is_public=public
    )
    await playlist.save()
    user = await models.User.get_or_create(ctx.author)
    await user.playlists.add(playlist)
    await user.save()
    await ctx.respond(f"`{playlist.name}` has been created.", embed=(await playlist.get_embed()))


@add.child()
@keikou.option("end", "The spot in the song where playback should end. If not specified, it will stop at the end.", type=str, default=-1)
@keikou.option("start", "The spot in the song where playback should start. If not specified, it will start at the beginning.", type=str, default=0)
@keikou.option("title", "The title of the song. If not specified, the title will be extrapolated from the source.", type=str, default=None)
@keikou.option("source", "The source for the song. See the help page about sources for more details.", type=str)
@keikou.option("playlist", "The name of the playlist to add the song to. Uses the selected playlist if not specified.", type=str, default=None)
@keikou.command("song", "Add a song to a playlist.")
@keikou.implements(keikou.SlashSubCommand)
async def add_song(ctx):
    playlist = await models.Playlist.get_or_none(owner=ctx.author, name=ctx.options.playlist)
    if not playlist:
        return await ctx.respond(f"You do not have a playlist named `{ctx.options.playlist}`.")
    
    entry = await playlist.items.all().get_or_none(source=ctx.options.source)
    if entry:
        return await ctx.respond("The entry could not be added. The source in the playlist matches the source of another entry:", embed=(await entry.get_embed()))

    start = ctx.options.start if ctx.options.start else 0
    end = ctx.options.end if ctx.options.end else -1
    
    entry = await models.PlaylistEntry.create(
        source=ctx.options.source,
        title=ctx.options.title,
        start=start,
        end=end,
    )
    await entry.save()
    await playlist.items.add(entry)
    await playlist.save()
    await ctx.respond(f"Added the following entry to `{playlist.name}`:", embed=(await entry.get_embed()))



@playlist.command()
@keikou.command("show", "Show something.")
@keikou.implements(keikou.SlashCommandGroup)
async def show(ctx):
    pass


@show.child()
@keikou.option("name", "The name of the playlist to show. If not specified, all playlists will be shown.", type=str, default=None)
@keikou.command("playlist", "Show a playlist, or all of your playlists.")
@keikou.implements(keikou.SlashSubCommand)
async def show_playlist(ctx):
    if ctx.options.name is not None:
        playlist = await models.Playlist.get_or_none(owner=ctx.author, name=ctx.options.name)
        if not playlist:
            return await ctx.respond(f"You don't have a playlist named `{ctx.options.name}`.")
        return await ctx.respond((await playlist.get_embed()))
    else:
        playlists = await models.Playlist.all().filter(owner=ctx.author)
        if not playlists:
            return await ctx.respond("You do not have any playlists defined.")
        content = ""
        for playlist in playlists:
            if not playlist.is_public:
                content += f"• [1;31m{playlist.name}[0m - [0;31m{playlist.description}[0m\n"
            else:
                content += f"• [1;34m{playlist.name}[0m - [0;34m{playlist.description}[0m\n"
        await ctx.respond(f"```ansi\n{content}```")


@playlist.command()
@keikou.command("delete", "Delete something.")
@keikou.implements(keikou.SlashCommandGroup)
async def delete(ctx):
    pass


@delete.child()
@keikou.option("name", "The name of the playlist to be deleted.")
@keikou.command("playlist", "Delete a playlist. THIS IS IRREVERSABLE.")
@keikou.implements(keikou.SlashSubCommand)
async def delete_playlist(ctx):
    playlist = await models.Playlist.get_or_none(owner=ctx.author, name=ctx.options.name)
    if not playlist:
        return await ctx.respond(f"You do not have a playlist named `{ctx.options.name}`.")

    msg = f"You are about to delete `{playlist.name}`. This action __CANNOT__ be undone. Are you sure?"
    menu = ValidationMenu()
    resp = await ctx.respond(msg, components=menu.build())
    await menu.start((await resp.message()))
    await menu.wait_for_input()

    if not menu.result:
        return await ctx.edit_last_response(menu.reason, components=[])
    
    await playlist.delete()
    await ctx.edit_last_response(f"`{playlist.name}` has been deleted.", components=[])



def load(bot):
    bot.add_plugin(playlist)


def unload(bot):
    bot.remove_plugin(playlist)