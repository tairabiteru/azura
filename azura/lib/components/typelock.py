import hikari
import miru

from .base import AuthorOnlyView
from ...mvc.games.models.typelock import Encounter, EncounterType, Type, TypeLock, TypeEmoji


class PokemonTypeSelect(miru.TextSelect):
    def __init__(self, encounter: Encounter, encounter_type: EncounterType, number: int):
        self.encounter = encounter
        self.encounter_type =  encounter_type
        self.number = number
        
        options = []
        current = None
        for type in self.encounter.choose_types(self.encounter_type, self.number):
            options.append(
                miru.SelectOption(
                    label=type.value, value=type.value, emoji=TypeEmoji[type.value].value
                )
            )

        super().__init__(
            options=options,
            placeholder=current
        )
    
    async def callback(self, ctx):
        selection = Type(self.values[0])
        embed = self.encounter.get_embed(self.encounter_type, selection)
        self.view.stop()
        await ctx.edit_response(embed, components=[])


class EncounterTypeSelect(miru.TextSelect):
    def __init__(self, encounter: Encounter):
        self.encounter = encounter
        
        options = []
        current = None

        for etype in self.encounter.possible_encounter_types:
            options.append(
                miru.SelectOption(
                    label=etype.value, value=etype.value
                )
            )

        super().__init__(
            options=options,
            placeholder=current
        )
    
    async def callback(self, ctx):
        selection = EncounterType(self.values[0])
        self.view.stop()

        if self.view.typelock.types_per_encounter == 1:
            type = self.encounter.choose_types(selection, 1)[0]
            embed = self.encounter.get_embed(selection, type=type)
            await ctx.respond(embed, components=[])
        else:
            embed = self.encounter.get_embed(selection)
            view = TypeLockPokemonTypeMenu(self.view.author, self.encounter, selection, self.view.typelock)
            await ctx.respond(embed, components=view)
            ctx.client.app.miru.start_view(view)


class TypeLockEncounterTypeMenu(AuthorOnlyView):
    def __init__(self, author: hikari.User, typelock: TypeLock, encounter: Encounter, timeout: int=None):
        super().__init__(author, timeout=timeout)
        self.encounter = encounter
        self.typelock = typelock

        self.add_item(EncounterTypeSelect(self.encounter))


class TypeLockPokemonTypeMenu(AuthorOnlyView):
    def __init__(self, author: hikari.User, encounter: Encounter, encounter_type: EncounterType, typelock: TypeLock, timeout: int=None):
        super().__init__(author, timeout=timeout)
        self.encounter = encounter
        self.encounter_type = encounter_type
        self.typelock = typelock

        self.add_item(PokemonTypeSelect(self.encounter, self.encounter_type, self.typelock.types_per_encounter))