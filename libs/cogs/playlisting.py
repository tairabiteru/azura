from libs.core.conf import settings
from libs.core.permissions import command
from libs.orm.playlist import *
from libs.orm.member import Member
from libs.orm.songdata import GlobalSongData
from libs.ext.player import YTDLSource

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
        if arg.startswith("--name:"):
            name = arg.replace("--name:", "").lstrip().rstrip()
        if arg.startswith("--playlists:"):
            playlists = arg.replace("--playlists:", "").lstrip().rstrip().split(",")
            playlists = list([playlist.lower().lstrip().rstrip() for playlist in playlists])
        if arg.startswith("--start:"):
            start = timecode_to_seconds(arg.replace("--start:", "").lstrip().rstrip())
        if arg.startswith("--end:"):
            end = timecode_to_seconds(arg.replace("--end:", "").lstrip().rstrip())
    return (generator, name, playlists, start, end)



class Playlisting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @command(aliases=['hist'])
    async def history(self, ctx, member : discord.Member=None):
        """Shows your listening history."""
        if not member:
            member = ctx.author
        output = "__:musical_note: " + member.name + "'s Last 15 Songs :musical_note:__\n```css\n"
        for i, entry in enumerate(reversed(Member.obtain(ctx.author.id).history)):
            output += str(i+1) + ". " + entry.split(":=:")[-1].strip() + "\n"
            if i+1 == 15:
                break
        await ctx.send(output + "```", delete_after=60)

    @command(aliases=['pladd', 'addpl', 'pla', 'apl'])
    async def add_playlist(self, ctx, *, name):
        """Creates a new playlist."""
        member = Member.obtain(ctx.author.id)
        try:
            member.add_playlist(name)
            await ctx.send("Playlist `" + name + "` has been added.")
        except PlaylistExistsError:
            await ctx.send("The specified playlist `" + name + "` already exists.")

    @command(aliases=['delpl', 'pldel', 'pld', 'dpl', 'rmplaylist', 'rmpl'])
    async def delete_playlist(self, ctx, *, name):
        """Deletes a playlist."""
        member = Member.obtain(ctx.author.id)
        try:
            member.delete_playlist(name)
            await ctx.send("Playlist `" + name + "` has been deleted.")
        except PlaylistNotFoundError:
            await ctx.send("The specified playlist `" + name + "` does not exist.")

    @command(aliases=['plshow', 'showpl', 'lspl'])
    async def show_playlist(self, ctx, *, name=None):
        """Shows all playlists, or shows a playlist if provided one."""
        member = Member.obtain(ctx.author.id)
        if not name:
            if len(member.playlist_names) == 0:
                return await ctx.send("You have not defined any playlists.")
            msg = "__Your Playlists__\nSelected playlist is displayed with a `#`\n\n"
            for playlist in member.playlist_names:
                if playlist == member.selected:
                    msg += " # " + playlist + "\n"
                else:
                    msg += " - " + playlist + "\n"
            return await ctx.send(msg)
        else:
            msg = "__" + name + "__\n"
            try:
                entries = member.entries_in_playlist(name)
            except PlaylistNotFoundError:
                return await ctx.send("The specified playlist `" + name + "` does not exist.")
            if not entries:
                return await ctx.send("There are no songs in `" + name + "`")
            for entry in member.entries_in_playlist(name):
                msg += " - " + entry.name + "\n"
            return await ctx.send(msg)

    @command(aliases=['adds', 'addsong'])
    async def add_song(self, ctx, *, cmdtext):
        """Adds an song to the selected playlist."""
        member = Member.obtain(ctx.author.id)
        generator, custom_title, playlists, start, end = parse_args(cmdtext)
        if not generator:
            return await ctx.send("Song generator not specified. You must specify either the search term that brings up the song you want, or you must specify the URL of the song.")

        if not member.selected and not playlists:
            return await ctx.send("You have not selected a playlist, nor have you specified a playlist to add this song to. You must do one or the other.")
        if not playlists:
            playlists = [member.selected]
        if any([playlist.lower() not in member.lower_playlist_names for playlist in playlists]):
            return await ctx.send("One of the playlists you specified does not exist.")

        src = await YTDLSource.create_source(ctx, generator)
        vid = src.id

        entry = PlaylistEntry(generator=generator, vid=vid, custom_title=custom_title, start_time=start, end_time=end, playlists=playlists)
        if member.vid_exists(vid):
            await ctx.send("Entry with existing VID found. Merging.")
        member.add_playlist_entry(entry)
        await ctx.send("Entry added.")

    @command(aliases=['rmsong', 'delsong', 'dels'])
    async def delete_song(self, ctx, *, title):
        """Removes a song from all playlists."""
        member = Member.obtain(ctx.author.id)
        try:
            entry = member.delete_playlist_entry(title)
            await ctx.send("Entry with VID `" + entry.vid + "` and generator `" + entry.generator + "` has been deleted.")
        except PlaylistEntryNotFoundError:
            await ctx.send("No entry with a generator or title of `" + title + "` was found.")

    @command(aliases=['rmplsong', 'delplsong'])
    async def delete_playlist_song(self, ctx, *, title):
        """Removes a song from the selected playlist."""
        member = Member.obtain(ctx.author.id)
        if not member.selected:
            return await ctx.send("You don't have a playlist selected.")
        try:
            entry = member.get_entry_by_title(title)
            try:
                entry.playlists.remove(member.selected)
                member.playlist_entries[entry.vid] = entry
                member.save()
                await ctx.send("`" + entry.name + "` removed from `" + member.selected + "`.")
            except ValueError:
                return await ctx.send("`" + entry.name + "` is not in the playlist `" + member.selected + "`.")
        except PlaylistEntryNotFoundError:
            await ctx.send("No entry by that name exists.")

    @command(aliases=['plsel', 'selpl', 'plselect', 'selectpl'])
    async def select_playlist(self, ctx, *, name):
        """Selects the specified playlist."""
        member = Member.obtain(ctx.author.id)
        if name.lower() not in member.lower_playlist_names:
            return await ctx.send("The specified playlist `" + name + "` does not exist.")

        name = member.get_proper_playlist_name(name)
        member.selected = name
        member.save()
        await ctx.send("`" + name + "` is now the selected playlist.")


def setup(bot):
    """Set up cog."""
    bot.add_cog(Playlisting(bot))
