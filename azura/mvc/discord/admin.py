from django.contrib import admin
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import User, Guild, Role, Channel, DiscordBaseModel, Locale, PermissionsObject, RoleGroup


class DiscordChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        return super().label_from_instance(obj)


class DiscordMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        return super().label_from_instance(obj)


class BaseDiscordForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = self.__class__.request
        for field in self.declared_fields.keys():
            if isinstance(self.declared_fields[field], DiscordChoiceField) or isinstance(self.declared_fields[field], DiscordMultipleChoiceField):
                self.declared_fields[field].request = self.request
        super().__init__(*args, **kwargs)

    class Meta:
        fields = '__all__'


class BaseDiscordAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        self.request = request
        return super().get_queryset(request)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        return form
    
    def get_readonly_fields(self, request, obj):
        if obj is None:
            return super().get_readonly_fields(request, obj)

        obj._bot = request.bot
        obj.resolve_all()

        for name in obj._get_field_value_map(obj._meta).keys():
            field = getattr(obj, name)
            if isinstance(field, DiscordBaseModel):
                field._bot = request.bot
                field.resolve_all()

        return super().get_readonly_fields(request, obj)


class UserForm(BaseDiscordForm):
    class Meta:
        model = User
        fields = "__all__"


class UserAdmin(BaseDiscordAdmin):
    list_display = ('name', 'id')
    form = UserForm
    readonly_fields = ('id', 'locale_settings')

    def name(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        try:
            return f"{obj.obj.username}#{obj.obj.discriminator}"
        except AttributeError:
            return f"Deleted UID: {obj.id}"


class GuildForm(BaseDiscordForm):
   class Meta:
       model = Guild
       fields = "__all__"


class GuildAdmin(BaseDiscordAdmin):
    list_display = ('name', 'id')
    form = GuildForm
    readonly_fields = ('id',)

    def name(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        return obj.obj.name


class ChannelForm(BaseDiscordForm):
    guild = DiscordChoiceField(queryset=Guild.objects.all())

    class Meta:
        model = Channel
        fields = "__all__"


class ChannelAdmin(BaseDiscordAdmin):
    form = ChannelForm
    list_display = ('name', 'id', 'guild_name')
    readonly_fields = ('id', 'guild', 'type')

    def name(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        return obj.obj.name
    
    def guild_name(self, obj):
        obj.guild._bot = self.request.bot
        obj.guild.resolve_all()
        return obj.guild.obj.name



class RoleForm(BaseDiscordForm):
    guild = DiscordChoiceField(queryset=Guild.objects.all())

    class Meta:
        model = Role
        fields = "__all__"


class RoleAdmin(BaseDiscordAdmin):
    list_display = ('name', 'id', 'guild_name')
    form = RoleForm
    readonly_fields = ('id', 'guild')

    def name(self, obj):
        obj._bot = self.request.bot
        obj.resolve_all()
        return obj.obj.name
    
    def guild_name(self, obj):
        obj.guild._bot = self.request.bot
        obj.guild.resolve_all()
        return obj.guild.obj.name


class RoleGroupForm(BaseDiscordForm):
    watched_roles = DiscordMultipleChoiceField(queryset=Role.objects.all(), required=False, widget=FilteredSelectMultiple(verbose_name=Role._meta.verbose_name, is_stacked=False))
    header_role = DiscordChoiceField(queryset=Role.objects.all(), required=False)

    class Meta:
        model = RoleGroup
        fields = "__all__"


class RoleGroupAdmin(BaseDiscordAdmin):
    list_display = ('name', 'header_role')
    form = RoleGroupForm


admin.site.register(User, UserAdmin)
admin.site.register(Guild, GuildAdmin)
admin.site.register(Channel, ChannelAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(Locale)
admin.site.register(PermissionsObject)
admin.site.register(RoleGroup, RoleGroupAdmin)