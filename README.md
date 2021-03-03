# Azura
Azura is a music bot created for my Discord server. She brings the good beats.

## Dependencies
* **Linux** - I use Kubuntu, though most distros will probably work fine as long as you can get Python running on them.
* **Python 3.7** - In production, I use Python 3.8.5, however as of Azura 2.5 R.8, she is now compatible with Python 3.7 and up. This allows compatibility with Pypy for increased *SPEED*.
* **A bunch of Python libraries** - They can be installed with:
```bash
pip3 install aiohttp aiohttp_jinja2 aiohttp_session beautifulsoup4 colorama cryptography discord.py[voice] jinja2 marshmallow python-pidfile pyfiglet toml wavelink
```
Please note that the `aiohttp` version __MUST__ be `3.6.2`. This is due to an issue with `aiohttp_session` which results in sessions being lost during HTTP redirects if the aiohttp version is higher than that.

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
* What changed in version 3.0?
  - A lot. The method Azura uses to enqueue songs and playlists is completely different, and should be threadsafe now. This allows for us to have some pretty fancy new enqueueing operations, which is the primary focus of this release.
* Why not just use some other music bot?
  - Writing my own allows me to give it a personal touch.
  - I can do more with this than I could with other music bots.
  - Where's the fun in that?
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
