from ext.utils import utcnow

import tortoise
import orm.models as models
import orm.fields as fields


class OpVars(models.HikariModel):
    """
    Operational Variables, or OpVars, are single variables or sets of variables
    that pertain specifically to the bot's operation, and which must persist
    past a full shutdown.
    """
    reinit_timestamp = tortoise.fields.DatetimeField(null=True)
    reinit_channel = fields.ChannelField(null=True)

    @classmethod
    async def get(cls):
        self, exists = await cls.get_or_create(id=1)
        return self

    @classmethod
    async def set_for_reinit(cls, channel):
        opvars = await cls.get()
        opvars.reinit_channel = channel
        opvars.reinit_timestamp = utcnow()
        await opvars.save()

    @classmethod
    async def clear_for_reinit(cls):
        opvars = await cls.get()
        opvars.reinit_timestamp = None
        opvars.reinit_channel = None
        await opvars.save()
