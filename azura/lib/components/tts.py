import hikari
import miru

from .base import AuthorOnlyView
from ...mvc.vox.models import VoxSettings
from ...mvc.discord.models import Channel
from ..tts import ALL_ENGINES


class BooleanButton(miru.Button):
    def __init__(self, settings: VoxSettings, field: str, text: str, position: int):
        self.settings = settings
        self.field = field

        if getattr(settings, field):
            style = hikari.ButtonStyle.SUCCESS
        else:
            style = hikari.ButtonStyle.DANGER

        super().__init__(
            label=text,
            style=style,
            position=position
        )
    
    async def callback(self, ctx):
        setattr(self.settings, self.field, not getattr(self.settings, self.field))
        await self.settings.asave() 
        await self.view.update(ctx)


class EngineSelect(miru.TextSelect):
    def __init__(self, settings: VoxSettings):
        self.settings = settings

        super().__init__(
            options=list([
                miru.SelectOption(label=engine.name, value=engine.abbrev) for engine in ALL_ENGINES
            ]),
            placeholder=self.settings.get_engine_cls().name
        )
    
    async def callback(self, ctx):
        self.settings.tts_engine = self.values[0]
        await self.settings.asave()
        await self.view.update(ctx)


class VoiceSelect(miru.TextSelect):
    def __init__(self, settings: VoxSettings):
        self.settings = settings
        engine = self.settings.get_engine_cls()
        current = self.settings.tts_voices.get(engine.abbrev, engine.DEFAULT_VOICE)

        super().__init__(
            options=list([
                miru.SelectOption(label=voice.title(), value=voice) for voice in engine.VOICES
            ]),
            placeholder=current.title()
        )

    async def callback(self, ctx):
        engine = self.settings.get_engine_cls()
        voices = self.settings.tts_voices

        voices[engine.abbrev] = self.values[0]
        self.settings._tts_voices = voices
        await self.settings.asave()
        await self.view.update(ctx)


class InputSelect(miru.TextSelect):
    def __init__(self, settings: VoxSettings):
        self.settings = settings

        options = []
        current = None
        for option in VoxSettings.INPUT_MODES:
            options.append(miru.SelectOption(label=f"{option[1]} Input", value=option[0]))
            if option[0] == self.settings.tts_input_mode:
                current = option[1]

        super().__init__(
            options=options,
            placeholder=f"{current} Input"
        )
    
    async def callback(self, ctx):
        if self.values[0] == 'CHAN':
            self.settings.tts_channel = await Channel.objects.aget(id=ctx.channel_id)
        
        self.settings.tts_input_mode = self.values[0]
        await self.settings.asave()
        await self.view.update(ctx)


class SpeedSelect(miru.TextSelect):
    def __init__(self, settings: VoxSettings):
        self.settings = settings
        
        options = []
        current = None

        for i in range(1, 11):
            if round(1 + i * 0.1, 1) == self.settings.tts_speed:
                current = f"{10 + i}0%"
    
            options.append(
                miru.SelectOption(label=f"{10 + i}0%", value=str(round(1 + (i * 0.1), 1)))
            )

        super().__init__(
            options=options,
            placeholder=current
        )
    
    async def callback(self, ctx):
        if float(self.values[0]) == 1:
            if "tempo" in self.settings.tts_sfx:
                self.settings.tts_sfx.pop("tempo")
        else:
            self.settings.tts_sfx["tempo"] = {'factor': float(self.values[0])}
    
        await self.settings.asave()
        await self.view.update(ctx)


class TTSOptionsMenu(AuthorOnlyView):
    def __init__(self, author: hikari.User, settings: VoxSettings, timeout: int=None):
        super().__init__(author, timeout=timeout)
        self.settings = settings

        self.add_item(BooleanButton(settings, "tts_prefix_username", "User Prefixing", 0))
        self.add_item(BooleanButton(settings, "tts_overdrive_all_caps", "Overdrive Caps", 1))
        self.add_item(BooleanButton(settings, "tts_apply_normal_sfx", "Apply SFX", 2))
        self.add_item(EngineSelect(settings))
        self.add_item(VoiceSelect(settings))
        self.add_item(InputSelect(settings))
        self.add_item(SpeedSelect(settings))
    
    async def update(self, ctx: miru.ViewContext):
        self.stop()
        view = self.__class__(self.author, self.settings, timeout=self.timeout)
        embed = await self.settings.get_embed(ctx.client.app, ctx.author.username)
        await ctx.edit_response(embed, components=view)
        ctx.client.app.miru.start_view(view)