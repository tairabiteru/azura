"""Main executable

This file starts the entire initialization process off, and comes with
the following commands:

    * install - Installs Farore's pipenv
    * test - Runs unit tests
    * mvc - Accesses the underlying Django MVC
    * run - Run Azura
    * multiplex - Run Azura in a GNU Screen instance
"""

from azura.core.conf import Config
from azura.core.install import install as f_install

import click
import os
import pidfile
import sys
from screenutils import Screen
import setproctitle
import uvloop


conf = Config.load()
os.chdir(conf.root_dir)


@click.group()
def azura():
    pass


@azura.command()
def multiplex():
    screen = Screen(conf.name.lower(), False)
    if screen.exists:
        print(f"There is already a screen session with the name {conf.name.lower()}. Please kill it before proceeding.")
        sys.exit(-1)
    
    screen.initialize()
    screen.send_commands(f"pipenv run \"python -O {conf.root} run && exit\"")
    sys.exit(0)


@azura.command()
@click.argument('subcommand', nargs=-1)
def mvc(subcommand):
    from azura.core.conf.loader import conf
    from django.core.management import execute_from_command_line
    execute_from_command_line([""] + sys.argv[2:])
    sys.exit(0)


@azura.command()
def test():
    from azura.tests.main import main
    main()


@azura.command()
def install():
    f_install()


@azura.command()
def run():
    try:
        uvloop.install()
        if os.path.exists(os.path.join(conf.root, "lock")):
            os.remove(os.path.join(conf.root, "lock"))

        from azura.core.bot import ParentBot
        bot = ParentBot(conf)

        with pidfile.PIDFile():
            setproctitle.setproctitle(conf.name)
            bot.run()
            if not os.path.exists(os.path.join(conf.root, "lock")):
                if os.path.exists(os.path.join(conf.root, "pidfile")):
                    os.remove(os.path.join(conf.root, "pidfile"))
                os.system(f"{sys.executable} {' '.join(sys.argv)}")
            else:
                bot.logger.warning("Lock file exists, permanent shutdown.")
            sys.exit(0)

    except pidfile.AlreadyRunningError:
        bot.logger.critical(f"{conf.name} is already running.")
    

if __name__ == "__main__":
    azura()
