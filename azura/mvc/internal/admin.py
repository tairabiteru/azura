from django.contrib import admin
from .models import OperationalVariables, Revision, FAQEntry, Child
from ..discord.models import Channel
from ..discord.admin import BaseDiscordForm, BaseDiscordAdmin, DiscordChoiceField
from asgiref.sync import async_to_sync


class OperationalVariablesForm(BaseDiscordForm):
    reinit_channel = DiscordChoiceField(queryset=Channel.objects.all(), required=False)

    class Meta:
        model = OperationalVariables
        fields = "__all__"


class OperationalVariablesAdmin(BaseDiscordAdmin):
    form = OperationalVariablesForm


class RevisionAdmin(admin.ModelAdmin):
    model = Revision
    ordering = ('-timestamp',)


class FAQEntryAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        rtn = super().save_model(request, obj, form, change)
        async_to_sync(request.bot.help.initialize)()
        return rtn


class ChildAdmin(admin.ModelAdmin):
    model = Child
    

admin.site.register(OperationalVariables, OperationalVariablesAdmin)
admin.site.register(Revision, RevisionAdmin)
admin.site.register(FAQEntry, FAQEntryAdmin)
admin.site.register(Child, ChildAdmin)