# Azura
Azura is a music bot created for my Discord server. While I'm unwilling to make the bot public, I'm willing to make her code open source so that others can host her if they want.

## Dependencies
* **Linux** - I use Kubuntu, though most distros will probably work fine as long as you can get Python running on them.
* **Python 3.8.5** - This is the version I use in production, but any version that satisfies the pip requirements and runs Discord.py will work fine.
* **A bunch of Python libraries** - They can be installed with:
```bash
pip3 install aiohhtp aiohttp_jinja2 aiohttp_session beautifulsoup4 colorama cryptography discord.py[voice] jinja2 marshmallow python-pidfile pyfiglet toml youtube-dl
```

## Installation
* Install the above dependencies.
* Copy the project contents to the desired folder.
* Run `python3 main.py`. This will result in a failure the first time, but will generate `settings.toml`
* This fill out the required settings in `settings.toml`, then run `python3 main.py` once more.
* `{botname}.sh` will be generated. Run `chmod +x {botname}.sh` to make it executable.
* Run `./{botname}.sh`

## Usage
You will probably want to grant yourself administrative permissions. They can be granted by editing the `acl` field of the owner's member file within `storage/database/members/`. Adding `bot.*: allow` will grant all permissions, though only certain commands need elevated permissions.

You can run `-help` for a list of all commands, and `-help [command]` to see details about a command.

## License
[GNU AGPLv3](https://choosealicense.com/licenses/agpl-3.0/)
