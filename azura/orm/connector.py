from orm.models.hikari import HikariModel

import tortoise


class ORM(tortoise.Tortoise):

    @classmethod
    async def init(cls, bot, *args, **kwargs):
        await super().init(*args, **kwargs)

        for name, model in cls.apps['models'].items():
            if isinstance(model, HikariModel) or hasattr(model, "attach_bot"):
                model.attach_bot(model, bot)
