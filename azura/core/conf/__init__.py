"""Core configuration definition

This file is responsible for defining the schema of conf.toml, a file
generated upon first initialization which defines operational settings for Farore.

    * __VERSION__ - Defines the major version of Farore
    * __TAG__ - Defines the 'tag' of the version

    * BaseConfig - A base schema which forces order in all inherited schemas
    * LoggingConfigSchema - Schema defining logging configuration
    * ORMConfigSchema - Schema defining configuration for the MVC
    * LavalinkConfigSchema - Schema defining configuration for lavalink
    * TRNGConfigSchema - Schema defining configuration for True Random Number Generation
    * AudioConfigSchema - Schema defining configuration for the audio plugin
    * ToolsConfigSchema - Schema defining configuration for the tools plugin
    * MinecraftConfigSchema - Schema defining configuration for the minecraft part of the admin plugin
    * AdminConfigSchema - Schema defining configuration for the admin plugin
    * GamesConfigSchema - Schema defining configuration for the games plugin
    * ProfileConfigSchema - Schema defining configuration for the profile plugin
    * PluginsConfigSchema - Schema defining configuration for all plugins
    * ConfigSchema - Schema defining the entire configuration
    * Config - Class which constructs the config namespace
"""

import aiofiles
import fernet
import os
from marshmallow import Schema, fields, post_load
from types import SimpleNamespace
from pathlib import Path
import toml


from .custom_fields import Timezone, ExistingPath, DiscordUID, LogLevel, TCPIPPort


__VERSION__ = "5.0"
__TAG__ = "Azure Aeon"


class BaseConfig(Schema):
    """BaseConfig simply forces ordering in any subclasses"""
    class Meta:
        ordered = True


class LoggingConfigSchema(BaseConfig):
    main_level = LogLevel(dump_default="INFO", required=True)
    hikari_level = LogLevel(dump_default="CRITICAL", required=True)
    mvc_level = LogLevel(dump_default="WARNING", required=True)
    log_format = fields.Str(dump_default='[%(asctime)s][%(levelname)s][%(name)s] %(message)s', required=True)
    date_format = fields.Str(dump_default="%x %X", required=True)


class ORMConfigSchema(BaseConfig):
    enable_http = fields.Boolean(dump_default=True, required=True)
    fernet_key = fields.Str(dump_default=fernet.Fernet.generate_key().decode("utf-8"), required=True)
    client_secret = fields.Str(dump_default="", required=True)
    host = fields.Str(dump_default="http://localhost", required=True)
    port = TCPIPPort(dump_default=8080, required=True)
    allowed_hosts = fields.List(fields.Str, required=True)
    static_root = ExistingPath(dump_default=os.path.join(os.getcwd(), "static/"), create=True, required=True)
    upload_root = ExistingPath(dump_default=os.path.join(os.getcwd(), "uploads/"), create=True, required=True)
    debug_mode = fields.Boolean(dump_default=True, required=True)
    db_backup_dir = ExistingPath(dump_default=os.path.join(os.getcwd(), "db_backups/"), create=True, required=True)
    db_host = fields.Str(dump_default="localhost", required=True)
    db_port = fields.Int(dump_default=5432, required=True)
    db_user = fields.Str(dump_default="", required=True)
    db_pass = fields.Str(dump_default="", required=True)
    db_name = fields.Str(dump_default="bot_database", required=True)


class LavalinkConfigSchema(BaseConfig):
    enabled = fields.Boolean(dump_default=False, required=True)
    host = fields.Str(dump_default="localhost", required=True)
    port = TCPIPPort(dump_default=2333, required=True)
    password = fields.Str(dump_default="", required=True)
    websocket_host = fields.Str(dump_default="localhost", required=True)
    websocket_port = TCPIPPort(dump_default=2334, required=True)
    disconnect_when_inactive_for = fields.Int(dump_default=300, required=True)


class TRNGConfigSchema(BaseConfig):
    enabled = fields.Boolean(dump_default=False, required=True)
    url = fields.Str(dump_default="", blank=True, required=True)
    endpoint = fields.Str(dump_default="", blank=True, required=True)


class ConfigSchema(BaseConfig):
    name = fields.Str(dump_default="Azura", required=True)
    prefix = fields.Str(dump_default=".", required=True)
    timezone = Timezone(dump_default="UTC", required=True)
    root = ExistingPath(dump_default=os.getcwd(), required=True)
    temp = ExistingPath(dump_default="/dev/shm/azura", create=True, required=True)
    logs = ExistingPath(dump_default=os.path.join(os.getcwd(), "logs/"), create=True, required=True)
    owner_id = DiscordUID(dump_default=100000000000000000, required=True)
    token = fields.Str(dump_default="", required=True)
    domain = fields.Str(dump_default="", required=True)
    enable_repl = fields.Bool(dump_default=True, required=True)
    logging = fields.Nested(LoggingConfigSchema, dump_default=LoggingConfigSchema().dump({}))
    mvc = fields.Nested(ORMConfigSchema, dump_default=ORMConfigSchema().dump({}))
    lavalink = fields.Nested(LavalinkConfigSchema, dump_default=LavalinkConfigSchema().dump({}))
    trng = fields.Nested(TRNGConfigSchema, dump_default=TRNGConfigSchema().dump({}))
    log_color = fields.Str(dump_default="cyan", required=True)

    @post_load
    def make(self, data, **kwargs):
        return Config.from_dict(data)


class Config(SimpleNamespace):
    def __init__(self, **entries):
        self.version = SimpleNamespace(**{'number': __VERSION__, 'tag': __TAG__})
        super().__init__(**entries)
    
    @property
    def root_dir(self):
        return Path(__file__).resolve().parent.parent.parent.parent
    
    @property
    def log_dir(self):
        return self.logs
    
    @property
    def asset_dir(self):
        return os.path.join(self.root, "assets/")
    
    @property
    def bin_dir(self):
        return os.path.join(self.root, "bin/")

    @property
    def outfacing_url(self):
        return self.mvc.allowed_hosts[0]
    
    @classmethod
    def from_dict(cls, d):
        for key, value in d.items():
            if isinstance(value, dict):
                d[key] = cls.from_dict(value)
            elif isinstance(value, list):
                d[key] = cls.from_list(value)
        return cls(**d)
    
    @classmethod
    def from_list(cls, l):
        for i, value in enumerate(l):
            if isinstance(value, list):
                l[i] = cls.from_list(value)
            elif isinstance(value, dict):
                l[i] = cls.from_dict(value)
        return l
    
    @classmethod
    async def aload(self):
        try:
            async with aiofiles.open('conf.toml', mode='r') as config_file:
                contents = await config_file.read()
                return ConfigSchema().load(toml.loads(contents))
        except FileNotFoundError:
            config_dict = ConfigSchema().dump({})
            async with aiofiles.open('conf.toml', mode='w') as config_file:
                await config_file.write(toml.dump(config_dict, config_file))
            return ConfigSchema().load(config_dict)
    
    @classmethod
    def load(self, orm=False):
        try:
            with open("conf.toml", "r") as config_file:
                conf = ConfigSchema().load(toml.load(config_file))
        except FileNotFoundError:
            config_dict = ConfigSchema().dump({})
            with open("conf.toml", "w") as config_file:
                toml.dump(config_dict, config_file)
            conf = ConfigSchema().load(config_dict)
        
        if orm is True:
            from ...mvc.core.settings import configure
            configure()
        return conf
