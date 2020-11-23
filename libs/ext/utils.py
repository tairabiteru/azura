from libs.core.conf import settings

import asyncio
from bs4 import BeautifulSoup
import calendar
import datetime
import errno
import math
import os
from PIL import Image
import pytz
import random
import re
import time
import urllib.request

def localnow():
    return datetime.datetime.now(pytz.timezone(settings['bot']['timezone']))

def urlretrieve(url, path):
    request = urllib.request.Request(url, headers={'User-Agent': "Magic Browser"})
    data = urllib.request.urlopen(request).read()
    with open(path, "wb") as out:
        out.write(data)
    return path

def getAvatar(user):
    path = urlretrieve(user.avatar_url, os.path.join(settings['bot']['tempDirectory'], "avatar.webp"))
    image = Image.open(path)
    image = image.convert("RGBA")
    return image

def reduceByteUnit(value):
    units = ['b/s', 'kb/s', 'Mb/s', 'Gb/s', 'Tb/s', 'Pb/s', 'Eb/s', 'Zb/s', 'Yb/s']
    unitIndex = 0
    while value > 1000:
        value /= 1000
        unitIndex += 1
    return "{value} {unit}".format(value=round(value), unit=units[unitIndex])

def isFloatDigit(number):
    return not any([char not in '0123456789.' for char in number])

def containsMention(text):
    matches = re.findall("<@![0-9]{18}>", text)
    matches += re.findall("<@[0-9]{18}>", text)
    return True if matches else False

def containsMentionOf(text, user):
    return user.mention.replace("!", "") in text

def replaceMentions(message):
    mentions = message.mentions
    content = message.content
    for mention in mentions:
        content = content.replace("<@{id}>".format(id=mention.id), "@{name} ({id})".format(name=mention.name, id=mention.id))
        content = content.replace("<@!{id}>".format(id=mention.id), "@{name} ({id})".format(name=mention.name, id=mention.id))
    return content

def cta(e):
    return e.replace("^", "**")

def strfdelta(delta, fmt):
    d = {'%d': str(delta.days)}
    d['%H'], r = divmod(delta.seconds, 3600)
    d['%H'] = str(d['%H'])
    d['%M'], d['%S'] = divmod(r, 60)
    d['%M'] = str(d['%M']) if d['%M'] > 9 else "0" + str(d['%M'])
    d['%S'] = str(d['%S']) if d['%S'] > 9 else "0" + str(d['%S'])
    return fmt.format(**d)

class TextTable:
    def __init__(self, rows=[], padding=1):
        self.rows = rows
        self.padding = padding

    @property
    def columns(self):
        return list(zip(*self.rows))

    @property
    def headers(self):
        return self.rows[0]

    def get_colw(self, col):
        lens = []
        for element in col:
            lens.append(len(str(element)))
        return max(lens)

    @property
    def rendered(self):
        table_by_column = []
        for column in self.columns:
            colw = self.get_colw(column)
            new_column = []
            for item in column:
                padding_needed = colw - len(str(item))
                item = str(item) + " " * padding_needed
                new_column.append(item)
            table_by_column.append(new_column)
        rows = list(zip(*table_by_column))
        table = ""
        for row in rows:
            padding = " " * self.padding
            line = "|"
            for item in row:
                line += padding + item + padding + "|"
            table += line + "\n"
        return table

def allMembers(bot):
    members = []
    for guild in bot.guilds:
        for member in guild.members:
            members.append(member)
    return members

def getUserGlobal(bot, uid):
    for member in allMembers(bot):
        if member.id == uid:
            return member

async def validate_operation(ctx, warning_msg, delete_sent=True, timeout=20):
    if delete_sent:
        await ctx.message.delete()
    firstRun = True
    wrong = False
    hex = "0123456789abcdef"
    hash = ""
    for i in range(0, 4):
        hash += random.choice(hex)
    while True:
        if firstRun:
            firstRun = False
            message = await ctx.send(warning_msg + "\n\n If you are **ABSOLUTELY POSITIVE** about this, please type in the following hash and hit enter within the next 20 seconds: `" + hash + "`")
        try:
            msg = await ctx.bot.wait_for('message', timeout=timeout)
            if ctx.author.id == msg.author.id and msg.channel.id == ctx.channel.id:
                if msg.content == hash:
                    await msg.delete()
                    await message.delete()
                    return True
                else:
                    await msg.delete()
                    await message.edit(content="Incorrect hash entered. Operation cancelled.")
                    return False
        except asyncio.TimeoutError:
            await message.edit(content="Timeout has elapsed. Operation cancelled.")
            return False

def parse_flags(cmdtext):
    args = cmdtext.split("--")
    playlist = args.pop(0).lstrip().rstrip()
    shuffle = False
    for arg in args:
        if "--" + arg == "--shuffle":
            shuffle = True
    return (playlist, shuffle)

def render_load_bar(progress, total, length=40):
    ratio = progress / total
    filled = "=" * int(length * ratio)
    unfilled = "-" * int(length - (length * ratio))
    return "`[" + filled + unfilled + "]`"

def human_bytes(bytes):
    power = 0
    labels = {0: 'B', 1: 'kB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while bytes > 2**10:
        bytes /= 2**10
        power += 1
    bytes = round(bytes, 2)
    return "{:,} {}".format(bytes, labels[power])
