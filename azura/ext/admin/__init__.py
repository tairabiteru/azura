import lightbulb

from .system import system
from .bot import bot
from .permissions import permissions
from .database import database


admin = lightbulb.Loader()

admin.command(system)
admin.command(bot)
admin.command(permissions)
admin.command(database)