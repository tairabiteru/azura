"""Main executable

This file starts the entire initialization process off, and comes with
the following commands:

    * mvc - Accesses the underlying Django MVC
    * run - Run azura directly.
    * daemon - Run azura as a daemon.
    * init_systemd - Create a SystemD service file.
    * init_bash - Create a bash script for the SystemD service.
"""
import click
import os
import pidfile
import sys
import setproctitle
import uvloop

from azura.core.conf import Config
from azura.core.log_base import get_base_logger


logger = get_base_logger()
conf = Config.load()


os.chdir(conf.root_dir)


def main(daemon=False):
    
    uvloop.install()
    
    if os.path.exists(os.path.join(conf.root, "lock")):
        os.remove(os.path.join(conf.root, "lock"))

    from azura.mvc.core.settings import configure
    configure()

    from azura.core.bot import Bot
    bot = Bot(conf)

    try:
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


@click.group()
def azura():
    pass


@azura.command()
@click.option('--exec_path', 'exec_path', default=f"./{conf.name.lower()}.sh")
@click.option('--uid', 'uid', default=os.getuid())
@click.option('--gid', 'gid', default=os.getgid())
@click.option('--stdout', 'stdout', default=f"{conf.logs}/{conf.name.lower()}.log")
@click.option('--stderr', 'stderr', default=f"{conf.logs}/{conf.name.lower()}.log")
@click.option('--output', 'output', default="./")
@click.option('--service_name', 'service_name', default=conf.name.lower())
def init_systemd(exec_path, uid, gid, stdout, stderr, output, service_name):
    from azura.core.init import generate_systemd_service

    generate_systemd_service(
        exec_path=exec_path,
        service_name=service_name,
        output_path=output,
        uid=uid,
        gid=gid,
        stdout_log_path=stdout,
        stderr_log_path=stderr
    )
    print("SystemD configuration generated.")


@azura.command()
@click.option('--script_name', 'script_name', default=f"{conf.name.lower()}.sh")
@click.option('--output', 'output', default="./")
@click.option('--exec_dir', 'exec_dir', default="./")
@click.option('--venv', 'venv', default=".venv")
def init_bash(script_name, output, exec_dir, venv):
    from azura.core.init import generate_bash_script

    generate_bash_script(
        script_name=script_name,
        output_path=output,
        exec_directory=exec_dir,
        venv_directory=venv
    )
    print("Bash script generated.")


@azura.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('subcommand', nargs=-1)
def mvc(subcommand):
    from azura.mvc.core.settings import configure
    configure()
    from django.core.management import execute_from_command_line
    execute_from_command_line([""] + sys.argv[2:])


@azura.command()
def run():
    main()


@azura.command()
def daemon():
    main(daemon=True)
    

if __name__ == "__main__":
    azura()