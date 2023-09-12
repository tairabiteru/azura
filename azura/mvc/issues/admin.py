from django.contrib import admin
from .models import Response, Issue
from ..discord.models import User
from ..discord.admin import BaseDiscordForm, BaseDiscordAdmin, DiscordChoiceField


class ResponseForm(BaseDiscordForm):
    author = DiscordChoiceField(queryset=User.objects.all())

    class Meta:
        model = Response
        fields = "__all__"


class ResponseAdmin(BaseDiscordAdmin):
    form = ResponseForm
    list_display = ('id', 'author')


class IssueForm(BaseDiscordForm):
    author = DiscordChoiceField(queryset=User.objects.all())

    class Meta:
        model = Issue
        fields = "__all__"


class IssueAdmin(BaseDiscordAdmin):
    form = IssueForm
    list_display = ('id', 'title', 'author')
    

admin.site.register(Response, ResponseAdmin)
admin.site.register(Issue, IssueAdmin)