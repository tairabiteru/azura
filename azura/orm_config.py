import toml

data = toml.load("conf.toml")

CONFIG = {
  "connections": {"default": data['postgres_uri']},
  "apps": {
    "models": {
      "models": ["orm.models", "aerich.models"],
      "default_connection": "default"
    }
  }
}