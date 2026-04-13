"""Module defining various utility functions and classes

This extension is basically a "miscellaneous" helper function file.
It largely contains things that don't fit anywhere else.

    * aio_get - Shortcut coroutine to performing an async GET request
    * aio_post - Same as above, but with POST instead
    * bearing_to_cardinal - Function which converts a compass bearing to a cardinal direction
    * coord_bearing - Function taking two pairs of coordinates and returning the compass bearing of the line drawn between them
    * coord_convert - Function taking a latitude and longitude and returning it in degree, minute, second format
    * coord_distance - Function taking two pairs of coordinates and returning the distance between them in miles
    * dir_size - Function which walks through a directory returning the size of its contents in bytes
    * execute_in_background - Shortcut function to add a coroutine to the event loop
    * get_byte_unit - Function taking a number of bytes and reducing it to the best unit (MB, GB, etc)
    * get_sha512_of - Function taking a path and returning the SHA512 hash digest of the contents of that path
    * get_lines_of - Function taking a path, and counting the total number of lines of the contents of that path
    * get_chars_of - Same as above, but with characters
    * is_all_caps - Function taking a string and returning a boolean telling if the text is entirely composed of capital letters
    * is_alphabet - Function taking a string and returning a boolean telling of the text is entirely made of alphabet characters
    * lint - Function which performs linting on all files contained under the path
    * ordinal - Function taking an integer and returning its ordinal form (ex: 1 -> 1st, 3 -> 3rd, etc...)
    * utcnow - Shortcut function to obtain the current UTC datetime object
    * icmp_ping - Function implementing abstraction of ICMP pinging
    * resize_for_upload - Function taking the path to an image and resizing it (if necessary) to be within Discord's upload limits
    * port_in_use - Function taking a TCP/IP port number and returning True if it is in use, and False otherwise
"""

import aiohttp
import asyncio
import datetime
import hikari
import os
from PIL import Image
import hashlib
import string
import subprocess
import socket
import tornado
import typing as t
import orjson as json


async def aio_get(
        url: str, 
        headers: t.Dict[str, str]={}, 
        format: str="text", 
        valid_responses: t.List[int]=[200],
        ssl: t.Optional[bool]=True
    ) -> t.Union[bytes, str, dict]:
    client = tornado.httpclient.AsyncHTTPClient()
    try:
        request = tornado.httpclient.HTTPRequest(
            url,
            headers=headers,
            validate_cert=ssl
        )
        response = await client.fetch(request)
    except tornado.httpclient.HTTPError as e:
        if e.code not in valid_responses:
            raise ValueError(f"Response code retrieving URL {url} was {e.code}.")
        raise
    
    if format == "bytes":
        return response.body
    elif format == "text":
        return response.body.decode("utf-8")
    elif format == "json":
        return json.loads(response.body.decode("utf-8"))
    else:
        raise ValueError(f"Unsupported format '{format}'.")


async def aio_post(
        url: str,
        data: dict={},
        headers: t.Dict[str, str]={},
        format: str="text",
        valid_responses: t.List[int]=[200],
        ssl: t.Optional[bool] = True
    ) -> t.Union[bytes, str, dict]:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, headers=headers, ssl=ssl) as response:
            if response.status not in valid_responses:
                raise ValueError(f"Response code retrieving URL {url} was {response.status}.")
            
            if format == "text":
                return await response.text()
            elif format == "json":
                return await response.json()
            elif format == "bytes":
                return await response.read()
            else:
                raise ValueError(f"Unsupported format: '{format}'.")


def get_dir_size(path: str) -> int:
    total = 0
    try:
        for root, _, files in os.walk(path):
            for file in files:
                file = os.path.join(root, file)
                if not os.path.islink(file):
                    total += os.path.getsize(file)
    except FileNotFoundError:
        return 0
    return total


def execute_in_background(func: t.Coroutine) -> asyncio.Task:
    loop = hikari.internal.aio.get_or_make_loop()
    return loop.create_task(func)


def get_byte_unit(numbytes: int, round_to: int=2) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    iterations = 0
    while numbytes >= 1000:
        numbytes /= 1000.0
        iterations += 1
    return f"{round(numbytes, round_to)} {units[iterations]}"


def get_sha512_of(
        path: str,
        restrict_to: t.List[str]=[],
        _hash: t.Optional[hashlib.sha512]=None
    ) -> t.Union[hashlib.sha512, str]:
    hash = _hash if _hash is not None else hashlib.sha512()
    if os.path.isdir(path):
        for subdir, _, fs in os.walk(path):
            for file in fs:
                if any([file.endswith(ext) for ext in restrict_to]) or restrict_to == []:
                    hash = get_sha512_of(os.path.join(subdir, file))
        return hash.hexdigest()
    else:
        with open(path, "rb") as file:
            hash.update(file.read())
            return hash


def get_lines_of(path: str, restrict_to: t.List[str]=[]) -> int:
    if os.path.isdir(path):
        lines = 0
        for subdir, _, fs in os.walk(path):
            for file in fs:
                if any([file.endswith(ext) for ext in restrict_to]) or restrict_to == []:
                    lines += get_lines_of(os.path.join(subdir, file))
        return lines
    else:
        with open(path, "rb") as file:
            lines = reversed(file.readlines())
            for i, line in enumerate(lines):
                if line == b"":
                    lines.pop(i)
                else:
                    break
            return len(lines)


def get_chars_of(path: str, restrict_to: t.List[str]=[]) -> int:
    if os.path.isdir(path):
        chars = 0
        for subdir, dirs, fs in os.walk(path):
            for file in fs:
                if any([file.endswith(ext) for ext in restrict_to]) or restrict_to == []:
                    chars += get_chars_of(os.path.join(subdir, file))
        return chars
    else:
        with open(path, "rb") as file:
            return len(file.readlines())


def is_all_caps(text: str) -> bool:
    return all([not char.islower() or not is_alphabet(char) for char in text]) and any([is_alphabet(char) for char in text])


def is_alphabet(text: str) -> bool:
    for char in text:
        if char not in string.ascii_uppercase and char not in string.ascii_lowercase:
            return False
    return True


def ordinal(number: int) -> str:
    return "%d%s" % (number, "tsnrhtdd"[(number//10 % 10 != 1) * (number % 10 < 4) * number % 10::4])


def strfdelta(
        delta: datetime.timedelta,
        fmt: str, 
        combine_days_and_hours: bool=False
    ):
    d = {"%d": str(delta.days)}
    d["%H"], r = divmod(delta.seconds, 3600)
    if combine_days_and_hours is True:
        d["%H"] = str(d["%H"] + delta.days * 24)
    else:
        d["%H"] = str(d["%H"])
    d["%M"], d["%S"] = divmod(r, 60)
    d["%M"] = str(d["%M"]) if d["%M"] > 9 else "0" + str(d["%M"])
    d["%S"] = str(d["%S"]) if d["%S"] > 9 else "0" + str(d["%S"])
    return fmt.format(**d)


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def icmp_ping(address: str, count: int=4) -> t.Generator[str, None, None]:
    process = subprocess.Popen(f"ping -c {count} {address}", stdout=subprocess.PIPE, shell=True)
    while True:
        line = process.stdout.readline().rstrip()
        if not line:
            break
        yield line.decode("utf-8")


def resize_for_upload(path: str, limit: int=10000000) -> None:
    if os.path.getsize(path) > limit:
        im = Image.open(path)
        w, h = im.size
        im = im.resize((int(w/2), int(h/2)))
        im.save(path)


def port_in_use(port: int, host: str="localhost") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def strfdelta_long(
        delta: datetime.timedelta,
        add_microseconds: bool=False
    ) -> str:
    components = ["", "", "", "", ""]

    if delta.days > 0:
        plural = "day" if delta.days == 1 else "days"
        components[0] = f"{delta.days} {plural}"
    if delta.seconds > 0:
        h, r = divmod(delta.seconds, 3600)
        m, s = divmod(r, 60)
        if h > 0:
            plural = "hour" if h == 1 else "hours"
            components[1] = f"{h} {plural}"
        if m > 0:
            plural = "minute" if m == 1 else "minutes"
            components[2] = f"{m} {plural}"
        if s > 0:
            plural = "second" if s == 1 else "seconds"
            components[3] = f"{s} {plural}"
    if delta.microseconds > 0:
        plural = "microsecond" if delta.microseconds == 1 else "microseconds"
        components[4] = f"{delta.microseconds} {plural}"
    
    if add_microseconds is False:
        components = components[0:4]
    components = [c for c in components if c != ""]

    output = ""
    for component in components:
        if component == components[-1] and len(components) != 1:
            output += f" and {component}"
        else:
            output += f" {component}"
    return output.strip()


def get_approx_timedelta(delta: datetime.timedelta) -> str:
    t = delta.total_seconds()

    if 0 <= t < 60:
        return "a few moments ago"
    elif 60 <= t < 3600:
        m = int(t // 60)
        s = "" if m == 1 else "s"
        return f"{m} minute{s} ago"
    elif 3600 <= t < 86400:
        h = int(t // 3600)
        s = "" if h == 1 else "s"
        return f"{h} hour{s} ago"
    elif 86400 <= t < 604800:
        d = int(t // 86400)
        s = "" if d == 1 else "s"
        return f"{d} day{s} ago"
    elif 604800 <= t < 2592000:
        w = int(t // 604800)
        s = "" if w == 1 else "s"
        return f"{w} week{s} ago"
    elif 2592000 <= t < 31536000:
        m = int(t // 2592000)
        s = "" if m == 1 else "s"
        return f"{m} month{s} ago"
    else:
        y = int(t // 31536000)
        s = "" if y == 1 else "s"
        return f"{y} year{s} ago"