from core.conf import conf

import aiohttp
import base64
from bs4 import BeautifulSoup
import datetime
import ipaddress
import os
from pylama.main import check_path, parse_options
import pytz
import re
import string
import subprocess


async def aio_get(url, headers={}, fmt="text"):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if fmt == "text":
                return await response.text()
            elif fmt == "json":
                return await response.json()
            elif fmt == "bytes":
                return await response.read()
            else:
                raise ValueError(f"Unsupported format '{fmt}'.")


def cleanGetParams(request):
    if "code" in request.rel_url.query:
        raise aiohttp.web.HTTPFound(str(request.rel_url).split("?")[0])


def commaSeparate(input):
    return "{:,}".format(int(input))


def dirSize(path):
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                file = os.path.join(root, file)
                if not os.path.islink(file):
                    total += os.path.getsize(file)
    except FileNotFoundError:
        return 0
    return total


async def getGenshinCodes(active=True):
    ENDPOINT = "https://genshin-impact.fandom.com/wiki/Promotional_Codes"
    response = await aio_get(ENDPOINT)
    tables = BeautifulSoup(response, "html.parser").findAll("table")
    for table in tables:
        if table.findAll("th")[0].html == "Code":
            break
    rows = table.findAll("tr")
    codes = []
    for row in rows:
        rowdata = row.findAll("td")
        rowdata = list([r.text.strip() for r in rowdata])
        if rowdata:
            codes.append(rowdata)
    finalcodes = []
    for code in codes:
        if "expired" not in code[3].lower() and active:
            finalcodes.append(code)
        elif not active:
            finalcodes.append(code)
    return finalcodes


async def getPublicIPAddr():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.ipify.org?format=json") as response:
            if response.status != 200:
                raise ValueError(f"Unable to get public IP address. Server returned status code {response.status}.")
            json = await response.json()
            return json['ip']


def image_as_b64url(path):
    filetype = path.split(".")[-1].lower()
    with open(path, "rb") as image:
        b64encoded = base64.b64encode(image.read()).decode()
    return f"data:image/{filetype};base64,{b64encoded}"


def lint(path):
    opts = {"linters": ["pyflakes"], "async": True}
    options = parse_options([path], **opts)
    return check_path(options, rootdir=".")


def localnow():
    return datetime.datetime.now(pytz.timezone(conf.timezone))


def ordinal(number):
    return "%d%s" % (number, "tsnrhtdd"[(number//10 % 10 != 1) * (number % 10 < 4) * number % 10::4])


def reduceByteUnit(numbytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    iterations = 0
    while numbytes >= 1024:
        numbytes /= 1024.0
        iterations += 1
    return f"{round(numbytes, 2)} {units[iterations]}"


def resolve(ctx, object):
    object = getattr(ctx.options, object)
    for user in ctx.resolved.users.values():
        if int(object) == int(user.id):
            return user
    for role in ctx.resolved.roles.values():
        if int(object) == int(role.id):
            return role
    for channel in ctx.resolved.channels.values():
        if int(object) == int(channel.id):
            return role
    raise ValueError("No object found.")


def strfdelta(delta, fmt):
    d = {"%d": str(delta.days)}
    d["%H"], r = divmod(delta.seconds, 3600)
    d["%H"] = str(d["%H"])
    d["%M"], d["%S"] = divmod(r, 60)
    d["%M"] = str(d["%M"]) if d["%M"] > 9 else "0" + str(d["%M"])
    d["%S"] = str(d["%S"]) if d["%S"] > 9 else "0" + str(d["%S"])
    return fmt.format(**d)


def icmpping(address, count=4):
    process = subprocess.Popen(f"ping -c {count} {address}", stdout=subprocess.PIPE, shell=True)
    while True:
        line = process.stdout.readline().rstrip()
        if not line:
            break
        yield line.decode("utf-8")


def arpscan(address):
    rtn = {}
    if os.name != 'posix':
        raise TypeError(f"Invalid operating system type '{os.name}'. This only works with 'posix'.")
    if not re.search("\/\d{1,2}", address[-3:]):
        address += "/32"
    if int(address[-2:]) > 32 or int(address[-2:]) < 1:
        raise ValueError(f"Invalid subnet mask `{address[-3:]}`. It must be between /1 and /32.")
    rtn['originalAddr'] = address
    try:
        addresses = [str(ip) for ip in ipaddress.IPv4Network(address)]
    except ValueError as e:
        if "Expected 4 octets" in str(e):
            raise ValueError(f"Invalid IP address: `{address[:-3]}`")
        raise ValueError(f"Invalid subnet mask `{address[-3:]}` for given address `{address[:-3]}`. The address has host bits set.")
    for addr in addresses:
        output = subprocess.run(["arp", "-a", addr], capture_output=True)
        output = output.stdout.decode("utf-8")
        if "no match found" in output:
            continue
        else:
            output = output.split(" at ")
            ipaddr, hwaddr = (output[0].split(" ")[-1].replace("(", "").replace(")", ""), output[1].split(" ")[0])
            rtn[ipaddr] = hwaddr
    return rtn


def isAlphabet(s):
    for char in s:
        if char not in string.ascii_uppercase and char not in string.ascii_lowercase:
            return False
    return True
