from libs.core.conf import conf

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
import socket

def localnow():
    return datetime.datetime.now(pytz.timezone(conf.timezone))

def urlretrieve(url, path):
    request = urllib.request.Request(url, headers={'User-Agent': "Magic Browser"})
    data = urllib.request.urlopen(request).read()
    with open(path, "wb") as out:
        out.write(data)
    return path

def getAvatar(user):
    path = urlretrieve(user.avatar_url, os.path.join(conf.tempDir, "avatar.webp"))
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

class Validation:
    def __init__(self, ctx, msg, delete_sent=True, timeout=20, security_length=4):
        self.ctx = ctx
        self.msg = msg
        self.delete_sent = delete_sent
        self.timeout = timeout
        self.security_length = security_length

    async def __aenter__(self):
        if self.delete_sent:
            await self.ctx.message.delete()
        firstRun = True
        wrong = False
        hex = "0123456789abcdef"
        hash = ""
        for i in range(0, self.security_length):
            hash += random.choice(hex)

        while True:
            if firstRun:
                message = await self.ctx.send("{msg} \n\nIf you're **ABSOLUTELY CERTAIN** about this, please type the following hash and hit enter within the next {time} seconds: `{hash}`".format(msg=self.msg, time=self.timeout, hash=hash))
                firstRun = False
            try:
                msg = await self.ctx.bot.wait_for('message', timeout=self.timeout)
                if self.ctx.author.id == msg.author.id and msg.channel.id == self.ctx.channel.id:
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

    async def __aexit__(self, *args):
        pass

class SimpleValidation:
    def __init__(self, ctx, msg, delete_sent=True, timeout=20):
        self.ctx = ctx
        self.msg = msg
        self.delete_sent = delete_sent
        self.timeout = timeout

    async def __aenter__(self):
        if self.delete_sent:
            await self.ctx.message.delete()
        firstRun = True
        while True:
            if firstRun:
                message = await self.ctx.send("{msg} \n\nIf you're **ABSOLUTELY CERTAIN** about this, please type `yes` and hit enter within the next {time} seconds. To cancel, type anything else.".format(msg=self.msg, time=self.timeout))
                firstRun = False
            try:
                msg = await self.ctx.bot.wait_for('message', timeout=self.timeout)
                if self.ctx.author.id == msg.author.id and msg.channel.id == self.ctx.channel.id:
                    if msg.content == "yes":
                        await msg.delete()
                        await message.delete()
                        return True
                    else:
                        await msg.delete()
                        await message.edit(content="Operation cancelled.")
                        return False
            except asyncio.TimeoutError:
                await message.edit(content="Timeout has elapsed. Operation cancelled.")
                return False

    async def __aexit__(self, *args):
        pass

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

def url_is_valid(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def ms_as_ts(ms):
    td = datetime.timedelta(seconds=(ms / 1000.0))
    if td.total_seconds() >= 86400:
        fmt = "{%d} {%H}:{%M}:{%S}"
    elif td.total_seconds() >= 3600:
        fmt = "{%H}:{%M}:{%S}"
    else:
        fmt = "{%M}:{%S}"
    return strfdelta(td, fmt)

def portIsOpen(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        s.shutdown(2)
        return True
    except:
        return False

def progressBar(num, denom, length=40):
    completion_ratio = float(num) / denom
    bars_completed = "=" * int(length * completion_ratio)
    bars_left = "-" * (length - len(bars_completed))
    return f"[{bars_completed}{bars_left}]"

def serializeTimestamp(ts):
    try:
        ts = int(ts)
        return ts
    except ValueError:
        pass

    ts = ts.split(":")
    if len(ts) not in [2, 3]:
        raise ValueError("Invalid timestamp specification.")

    multiplier = 1
    total = 0
    for segment in reversed(ts):
        segment = int(segment)
        if segment < 0:
            raise ValueError("Segments must be positive.")
        total += segment * multiplier
        multiplier *= 60
    return total
