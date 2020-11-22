"""Module that defines the dashboard."""

from libs.core.conf import settings
from libs.dash.routes import routes

from aiohttp import web
import aiohttp_jinja2
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
from cryptography import fernet
import jinja2


class Dash:
    """
    Class defines the dashboard.

    We basically use this class to wrap aiohttp and allow it to be
    bolted onto the bot object after it is initialized.
    """

    def __init__(self, bot):
        """Initialize dashboard."""
        self.bot = bot
        self.host = settings['dash']['host']
        self.port = settings['dash']['port']
        self.templateDirectory = settings['dash']['templateDirectory']
        self.staticDirectory = settings['dash']['staticDirectory']

    async def setup(self):
        """Perform setup."""
        self.app = web.Application()
        self.app.bot = self.bot

        aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader(self.templateDirectory))

        fernet_key = fernet.Fernet.generate_key()
        secret_key = base64.urlsafe_b64decode(fernet_key)
        aiohttp_session.setup(self.app, EncryptedCookieStorage(secret_key))

        self.app.router.add_static('/static/', path=self.staticDirectory, name='static')
        self.app.add_routes(routes)
