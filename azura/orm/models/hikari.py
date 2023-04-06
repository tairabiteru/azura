from orm.fields import HikariMixin

import tortoise


class HikariModel(tortoise.models.Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def attach_bot(self, bot):
        self.bot = bot

        for name, field in self._meta.fields_map.items():
            if isinstance(field, HikariMixin):
                field.bot = bot
