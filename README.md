# Azura
Azura is a music bot created for my Discord server. She brings the good beats.

## What changed in Version 2.0?
* Like, literally everything. She might as well not even be the same bot. Azura is no longer based on YTDL, but is now based on [Wavelink](https://github.com/PythonistaGuild/Wavelink).
* Also important to note, this is a massive work in progress. There will inevitably be some broken things.

## Dependencies
* **Linux** - I use Kubuntu, though most distros will probably work fine as long as you can get Python running on them.
* **Python 3.8.5** - This is the version I use in production, but any version that satisfies the pip requirements and runs Discord.py will work fine.
* **A bunch of Python libraries** - They can be installed with:
```bash
pip3 install aiohttp aiohttp_jinja2 aiohttp_session beautifulsoup4 colorama cryptography discord.py[voice] jinja2 marshmallow python-pidfile pyfiglet toml wavelink
```

## Installation
* Install the above dependencies.
* Copy the project contents to the desired folder.
* Download [Lavalink](https://github.com/Frederikam/Lavalink), put jar into `bin/` folder.
* Create an `application.yml` file for Lavalink, fill out desired settings.
* Run `python3 main.py`. This will result in a failure the first time, but will generate `settings.toml`
* Fill out the required settings in `settings.toml`, including the Lavalink settings, then run `python3 main.py` once more.
* `{botname}.sh` will be generated. Run `chmod +x {botname}.sh` to make it executable.
* Run `./{botname}.sh`

## Usage
You will probably want to grant yourself administrative permissions. They can be granted by editing the `acl` field of the owner's member file within `storage/database/members/`. Adding `bot.*: allow` will grant all permissions, though only certain commands need elevated permissions.

You can run `-help` for a list of all commands, and `-help [command]` to see details about a command.

## Questions I've not been asked, but will probably be asked anyway.
* Why'd version 2.0 switch away from YTDL?
  * Because YTDL has too many issues, and Lavalink is about a million times better, both in functionality and in quality of stream. Even if I were perfect at writing bots with it, there's no way I could do everything I can with Lavalink.
  * The only downside of Lavalink is that it requires a lot more RAM. In fact, expect Azura to use upwards of a gigabyte when enqueueing songs. I'm willing to make that sacrifice for the superior audio quality and functionality. Take my RAM. Take two, if you want.
* Your code is messy.
  1. That's not a question.
  2. Yeah, I know. I'll refine it in future versions. I wrote all this in like, a week, and was in a rush to do so to have a bot to play Christmas music with.
* Why not just use some other music bot?
  1. Where's the fun in that?
  2. Writing my own allows me to give it a personal touch.
  3. I can do more with this than other music bots can.
  4. I'm probably insane.
* How can I add this bot to my server?
  * You can't. Azura is a private bot for a private server. If you want, you're more than welcome to run the bot yourself.
* Aww, that's a lot of work though. Can't you make her public?
  * No.
* Why?
  * Because while I'm perfectly willing to share my code with the world, my server does a lot more than just run music bots all day. Go get your own damn RAM.
* How do you get the dash to work?
  * The dash operates on an internal webserver that is disabled by default. When enabled it runs (by default) on `localhost:8080`. All of these settings can be found in `settings.toml`. Once started, the internal webserver can either be accessed directly at the appropriate address in a web browser, or it can be reverse proxied through a proper webserver like Apache 2. I won't explain that process here. 
* Can this be run on Macrosoft&reg; Winders&trade;?
  * Azura's code basically requires bash scripting and assumes Unix paths. If you want to rewrite her bash file in batch and also change the relevant parts of her code, go ahead. But barring that, no: she requires Linux.
* What's the meaning behind the name?
  * She's named after [Azura](https://fireemblem.fandom.com/wiki/Azura), a character in Fire Emblem whose class is "Songstress." I'll let you connect the rest of the dots.

## License
[GNU AGPLv3](https://choosealicense.com/licenses/agpl-3.0/)
