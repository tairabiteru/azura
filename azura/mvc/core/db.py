import os

from ...core.conf import Config


conf = Config.load()


def dump_database(fname: str) -> bool:
    userpath = os.path.expanduser("~/")
    if not os.path.exists(os.path.join(userpath, ".pgpass")):
        with open(os.path.join(userpath, ".pgpass"), "w") as pgpassfile:
            pgpassfile.write(f"{conf.mvc.db_host}:{conf.mvc.db_port}:{conf.mvc.database.name}:{conf.mvc.database.user}:{conf.mvc.database.password}")
        os.system(f"chmod 600 {os.path.join(userpath, '.pgpass')}")
    else:
        with open(os.path.join(userpath, ".pgpass"), "r") as pgpassfile:
            lines = pgpassfile.readlines()
        if f"{conf.mvc.database.host}:{conf.mvc.database.port}:{conf.mvc.database.name}:{conf.mvc.database.user}:{conf.mvc.database.password}" not in lines:
            with open(os.path.join(userpath, ".pgpass"), "a") as pgpassfile:
                pgpassfile.write(f"{conf.mvc.database.host}:{conf.mvc.database.port}:{conf.mvc.database.name}:{conf.mvc.database.user}:{conf.mvc.database.password}")

    os.system(f"pg_dump -U {conf.mvc.database.user} -h {conf.mvc.database.host} -p {conf.mvc.database.port} {conf.mvc.database.name} -w >> {os.path.join(conf.mvc.database.backup_dir, fname)}")
    return True