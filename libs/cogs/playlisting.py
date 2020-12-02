from libs.core.conf import settings
from libs.core.permissions import command
from libs.orm.member import Member, PlaylistExists, PlaylistNotFound, EntryExists, EntryNotFound
from libs.orm.playlist import PlaylistEntry
from libs.orm.songdata import GlobalSongData
from libs.ext.utils import SimpleValidation

import discord
from discord.ext import commands

def timecode_to_seconds(timecode):
    timecode = timecode.split(":")
    if len(timecode) == 1:
        return int(timecode[0])
    else:
        if len(timecode) > 3:
            raise ValueError("Invalid timecode.")
        total = 0
        if len(timecode) == 2:
            multiplier = 60
        else:
            multiplier = 3600
        for component in timecode:
            total += int(component) * multiplier
            multiplier /= 60
        return int(total)

def parse_args(string):
    args = string.split("--")
    generator = args.pop(0).lstrip().rstrip()
    name = ""
    playlists = []
    start = 0
    end = -1
    args = list(["--" + arg.lstrip().rstrip() for arg in args])
    for arg in args:
        if arg.startswith("--name"):
            name = arg.replace("--name", "").lstrip().rstrip()
        if arg.startswith("--playlists"):
            playlists = arg.replace("--playlists", "").lstrip().rstrip().split(",")
            playlists = list([playlist.lower().lstrip().rstrip() for playlist in playlists])
        if arg.startswith("--start"):
            start = timecode_to_seconds(arg.replace("--start", "").lstrip().rstrip())
        if arg.startswith("--end"):
            end = timecode_to_seconds(arg.replace("--end", "").lstrip().rstrip())
    return (generator, name, playlists, start, end)



class Playlisting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @command(aliases=['hist'])
    async def history(self, ctx, member : discord.Member=None):
        """
        Syntax: `{pre}{command_name} [@member]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Displays the history of songs that have been played by the specified member.
        If no member is specified, it defaults to the command executor.

        __**Arguments**__
        `[@member]` - The member whose history you want to see. If no member is
        specified, it defaults to the command executor.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} @Taira`
        """
        if not member:
            member = ctx.author
        output = f"__:musical_note: {member.name}'s Last 15 Songs :musical_note:__\n```css\n"
        member = Member.obtain(member.id)
        for i, entry in enumerate(reversed(member.history)):
            output += f"{i+1}. {entry}\n"
            if i+1 == 15:
                output += '```'
                break
        return await ctx.send(output)

    @command(aliases=['pladd', 'addpl', 'pla', 'apl'])
    async def add_playlist(self, ctx, *, name):
        """
        Syntax: `{pre}{command_name} <name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Adds a new playlist with the specified name.

        __**Arguments**__
        `<name>` - The name of the playlist to be created.

        __**Example Usage**__
        `{pre}{command_name} Electronic Music`
        `{pre}{command_name} Lo-Fi`
        """
        member = Member.obtain(ctx.author.id)
        try:
            member.add_playlist(name)
            await ctx.send("Playlist `" + name + "` has been added.")
        except PlaylistExists:
            await ctx.send("The specified playlist `" + name + "` already exists.")

    @command(aliases=['delpl', 'pldel', 'pld', 'dpl', 'rmplaylist', 'rmpl'])
    async def delete_playlist(self, ctx, *, name):
        """
        Syntax: `{pre}{command_name} <name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Deletes the new playlist with the specified name.

        __**Arguments**__
        `<name>` - The name of the playlist to be deleted.

        __**Example Usage**__
        `{pre}{command_name} Electronic Music`
        `{pre}{command_name} Lo-Fi`
        """
        member = Member.obtain(ctx.author.id)
        if not member.playlist_exists(name):
            return await ctx.send(f"No playlist named `{name}` exists.")
        if len(member.playlists[name]) == 0:
            member.del_playlist(name)
        else:
            warning = f"You are about to delete the playlist `{name}`, which still has songs in it. This action is __NOT REVERSABLE__."
            async with SimpleValidation(ctx, warning) as validation:
                if not validation:
                    return await ctx.send("Operation cancelled.")
                else:
                    member.del_playlist(name)
        return await ctx.send(f"The playlist `{name}` has been deleted.")


    @command(aliases=['plshow', 'showpl', 'lspl'])
    async def show_playlist(self, ctx, *, name=None):
        """
        Syntax: `{pre}{command_name} [name]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Lists the specified playlist. If no playlist is specified, it lists all
        playlists. A playlist with `🠊` in front of its name is the selected
        playlist.

        __**Arguments**__
        `[name]` - The name of the playlist to be displayed. If not specified,
        all playlists are shown.

        __**Example Usage**__
        `{pre}{command_name}`
        `{pre}{command_name} Lo-Fi`
        """
        member = Member.obtain(ctx.author.id)
        try:
            return await ctx.send(embed=member.playlist_embed(name=name))
        except PlaylistNotFound:
            return await ctx.send(f"The specified playlist `{name}` does not exist.")

    @command(aliases=['adds', 'addsong'])
    async def add_song(self, ctx, *, cmdtext):
        """
        Syntax: `{pre}{command_name} <generator> [--options]`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Adds a song to the currently selected playlist with the specified options.
        The URL or search term specified should go to the song. (When `{pre}play`
        is run with the search term or URL, the desired song should play.)

        This command has a lot of options which can  be specified after the URL
        or search term that change certain things about how the song is stored:

        `--name <name>` - When specified, it overrides the default title of the
        video. This can be useful if the video title is long, or you want the name
        displayed in the playlist to be different.

        `--playlists <playlists>` - When specified, it overrides the default
        playlist that the song is added to. This is useful for when you want to
        add a song to multiple playlists at once. Playlists are specified by
        separating them with commas.

        `--start <starttime>` - When specified, the bot will start the video at
        the specified timestamp. If not specified, it defaults to the beginning
        of the video.

        `--end <endtime>` - When specified, the bot will end the video at the
        specified timestamp. If not specified, it defaults to the end of the
        video.

        __**Arguments**__
        `<generator>` - The URL or search term that spawns the song to be
        added. To know what URLs can be used, run `{pre}help play`.
        `[--options]` - Any of the options listed above. The order they are
        specified in, or whether or not all are specified does not matter.

        __**Example Usage**__
        `{pre}{command_name} South Park - Kyle's Mom's a Bitch`
        `{pre}{command_name} https://www.youtube.com/watch?v=aiSdTQ9DW9g --name Boney M. - Rasputin`
        `pre -adds https://www.youtube.com/watch?v=XFg43JqWmdM --name Pokemon Diamond and Pearl: Pokemon League (Night) Lo-Fi --playlists Lo-Fi, VGM --end: 4:32`
        """
        member = Member.obtain(ctx.author.id)
        generator, custom_title, playlists, start, end = parse_args(cmdtext)
        if not generator:
            return await ctx.send("Song generator not specified. The generator is the URL or search term that spawns the video.")
        if not member.selected and not playlists:
            return await ctx.send("You have not selected a playlist, nor have you specified a playlist to add this song to. You must do one or the other.")
        if not playlists:
            playlists = [member.selected]

        fakeplaylists = []
        for playlist in playlists:
            if not member.playlist_exists(playlist):
                fakeplaylists.append(playlist)
        if any(fakeplaylists):
            fakeplaylists = "`, `".join(fakeplaylists)
            return await ctx.send(f"The following playlists you specified do not exist:\n`{fakeplaylists}`")
        try:
            entry = PlaylistEntry(generator=generator, custom_title=custom_title, start_time=start, end_time=end)
            for playlist in playlists:
                member.add_playlist_entry(playlist, entry)
            return await ctx.send("Entry added:", embed=entry.embed(member))
        except EntryExists:
            return await ctx.send("The name or generator already exists in the selected or specified playlists.")

    @command(aliases=['rmsong', 'delsong', 'dels'])
    async def delete_song(self, ctx, *, title):
        """
        Syntax: `{pre}{command_name} <name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Removes the specified song from __ALL__ playlists. The song entered
        must __EXACTLY MATCH__ the title listed in the playlists. This command is
        distinguished from `{pre}delete_playlist_song` by the fact that it deletes
        the specified song from *ALL* playlists. **As a result, caution should be
        excersized when using this command.**

        __**Arguments**__
        `<name>` - The name of the song to be deleted.

        __**Example Usage**__
        `{pre}{command_name} Boney M. - Rasputin`
        """
        member = Member.obtain(ctx.author.id)
        try:
            if len(member.member_playlists(title)) > 1:
                warning = "This command deletes songs from __ALL__ playlists, and this song is apart of more than one playlist. This action is also not reversable."
                async with SimpleValidation(ctx, warning) as validation:
                    if not validation:
                        return await ctx.send("Operation cancelled.")
            entries = member.delete_from_all(title)
            return await ctx.send(f"Deleted `{title}` from {len(entries)} playlist(s).")
        except EntryNotFound:
            await ctx.send(f"No entry with a generator or title of `{title}` was found.")

    @command(aliases=['rmplsong', 'delplsong'])
    async def delete_playlist_song(self, ctx, *, title):
        """
        Syntax: `{pre}{command_name} <name>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Removes the specified song from the __SELECTED__ playlist. The song entered
        must __EXACTLY MATCH__ the title listed in the playlist. This command is
        distinguished from `{pre}delete_song` by the fact that it only deletes
        from the *selected* playlist, and not all playlists.

        __**Arguments**__
        `<name>` - The name of the song to be deleted.

        __**Example Usage**__
        `{pre}{command_name} Boney M. - Rasputin`
        """
        member = Member.obtain(ctx.author.id)
        if not member.selected:
            return await ctx.send("You don't have a playlist selected.")
        try:
            entry = member.delete_playlist_entry(member.selected, title)
            return await ctx.send(f"Removed `{title}` from `{member.selected}`.")
        except EntryNotFound:
            await ctx.send(f"No entry identified by `{title}` exists.")

    @command(aliases=['plsel', 'selpl', 'plselect', 'selectpl'])
    async def select_playlist(self, ctx, *, name):
        """
        Syntax: `{pre}{command_name} <playlist>`

        **Aliases:** `{aliases}`
        **Node:** `{node}`
        **Grant Level:** `{grant_level}`

        __**Description**__
        Selects the specified playlist. This is used for operations which require
        a selected playlist. It will cause a playlist to appear with a `#` in front
        of it when `{pre}show_playlist` is run.

        __**Arguments**__
        `<playlist>` - The name of the song to be deleted.

        __**Example Usage**__
        `{pre}{command_name} Lo-Fi`
        """
        member = Member.obtain(ctx.author.id)
        if not member.playlist_exists(name):
            return await ctx.send(f"The specified playlist `{name}` does not exist.")
        name, _ = member.get_playlist(name)
        member.selected = name
        member.save()
        await ctx.send(f"`{name}` is now the selected playlist.")


def setup(bot):
    """Set up cog."""
    bot.add_cog(Playlisting(bot))
