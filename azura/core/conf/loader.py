"""Module acts as a shortcut to loading the config

By importing 'conf' from this module, you can skip the instantiation
of the config itself. This is useful in certain circumstances, but has to
be used with care because this file loads ORM configuration.

This is normally fine, but certain models and files within the MVC also need
to load the config, and loading this within the MVC generally results in a
circular import error. This same error can also occur in other files outside
of the MVC if they also import from the MVC. So be careful.

    * conf - The loaded configuration, with ORM support
"""

from . import Config


conf = Config.load(orm=True)