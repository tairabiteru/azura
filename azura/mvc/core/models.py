from asgiref.sync import sync_to_async
from django.db import models


class BaseAsyncModel(models.Model):

    class Meta:
        abstract = True
    
    async def asave(self, *args, **kwargs):
        return await sync_to_async(super().save)(*args, **kwargs)
    
    async def adelete(self, *args, **kwargs):
        return await sync_to_async(super().delete)(*args, **kwargs)