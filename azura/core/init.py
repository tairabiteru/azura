import grp
import os
import pwd

from .conf import Config


conf = Config.load()


def generate_bash_script(
    script_name: str = f"{conf.name.lower()}.sh",
    output_path: str = "./",
    exec_directory: str = "./",
    venv_directory: str = ".venv",
) -> None:
    output_path = os.path.abspath(os.path.join(output_path, script_name))
    exec_directory = os.path.abspath(exec_directory)
    venv_directory = os.path.abspath(venv_directory)

    with open(os.path.join(conf.asset_dir, "bash.template"), 'r') as template:
        template = template.read()

    data = {
        'exec_directory': exec_directory,
        'venv_directory': venv_directory
    }

    with open(output_path, 'w') as service:
        out = template.format(**data)
        service.write(out)



def generate_systemd_service(
        service_name: str = conf.name.lower(),
        output_path: str = "./",
        exec_path: str = f"./{conf.name.lower()}.sh",
        uid: int = os.getuid(),
        gid: int = os.getgid(),
        stdout_log_path: str = f"./logs/{conf.name.lower()}.log",
        stderr_log_path: str = f"./logs/{conf.name.lower()}.log"
) -> None:
    user = pwd.getpwuid(uid).pw_name
    group = grp.getgrgid(gid).gr_name

    output_path = os.path.abspath(os.path.join(output_path, f"{service_name}.service"))
    exec_path = os.path.abspath(exec_path)
    stdout_log_path = os.path.abspath(stdout_log_path)
    stderr_log_path = os.path.abspath(stderr_log_path)

    with open(os.path.join(conf.asset_dir, "systemd.template"), 'r') as template:
        template = template.read()

    data = {
        'exec_path': exec_path,
        'user': user,
        'group': group,
        'stdout_log_path': stdout_log_path,
        'stderr_log_path': stderr_log_path,
        'uid': uid
    }

    with open(output_path, 'w') as service:
        out = template.format(**data)
        service.write(out)