import asyncio
import discord

async def paginate_embed(ctx, embed, contents, threshold=1900):
    etitle = embed.title
    edescription = embed.description
    ecolor = embed.color
    efields = embed.fields
    current_chars = len(etitle) + len(edescription)
    current_page = []
    pages = []
    for name, value in [(row[0], row[1]) for row in contents]:
        if current_chars + len(name) + len(value) > threshold:
            pages.append(current_page)
            current_page = [(name, value)]
            current_chars = len(etitle) + len(edescription) + len(name) + len(value)
        else:
            current_page.append((name, value))
            current_chars += len(name) + len(value)
    pages.append(current_page)

    embed_pages = []
    for page in pages:
        embed = discord.Embed(title=etitle, description=edescription, color=ecolor)
        for field in efields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)
        for name, value in page:
            embed.add_field(name=name, value=value, inline=False)
        embed_pages.append(embed)
    pages = embed_pages

    firstRun = True
    while True:
        if firstRun:
            firstRun = False
            page_number = 1

            if len(pages) == 1:
                message = await ctx.send(embed=embed)
                break
            else:
                message = await ctx.send("`Page " + str(page_number) + " of " + str(len(pages)) + "`", embed=pages[0])

        if page_number == len(pages):
            await message.add_reaction('\N{Leftwards Black Arrow}')
        elif page_number == 1:
            await message.add_reaction('\N{Black Rightwards Arrow}')
        else:
            await message.add_reaction('\N{Leftwards Black Arrow}')
            await message.add_reaction('\N{Black Rightwards Arrow}')

        def checkReaction(reaction, user):
            return reaction.emoji in ['\N{Leftwards Black Arrow}', '\N{Black Rightwards Arrow}']

        try:
            reaction, user = await ctx.bot.wait_for('reaction_add', check=checkReaction, timeout=60)
            if user.id == ctx.author.id:
                if reaction.emoji == '\N{Leftwards Black Arrow}':
                    page_number -= 1
                elif reaction.emoji == '\N{Black Rightwards Arrow}':
                    page_number += 1

                await message.delete()
                message = await ctx.send("`Page " + str(page_number) + " of " + str(len(pages)) + "`", embed=pages[page_number-1])

        except asyncio.TimeoutError:
            break
