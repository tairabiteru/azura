from .utils import generate_loading_bar, generate_volume_bar, timestamp_from_ms
import hikari
import miru


class PlayerControls(miru.View):
    def __init__(self, session, *args, **kwargs):
        self.session = session
        super().__init__(*args, **kwargs)
    
    @miru.button(label="⏮️", style=hikari.ButtonStyle.PRIMARY)
    async def last_track(self, button, ctx):
        await self.session.skip(by=-1, button=True)
    
    @miru.button(label="⏹️", style=hikari.ButtonStyle.DANGER)
    async def stop_btn(self, button, ctx):
        await self.session.disconnect()
    
    @miru.button(label="⏯️", style=hikari.ButtonStyle.PRIMARY)
    async def toggle_pause(self, button, ctx):
        await self.session.pause_cmd(not self.session._is_paused)
    
    @miru.button(label="⏭️", style=hikari.ButtonStyle.PRIMARY)
    async def next_track(self, button, ctx):
        await self.session.skip(by=1, button=True)


class PlayerEmbed:
    def __init__(self, session):
        self.session = session
    
        self._message = None
        self._completed = False
        self._stopped = False
        self._controls = PlayerControls(self.session, timeout=None)
        self._current_track = session._current_track
    
    @property
    def track_progress_bar(self):
        if self._completed is True:
            return generate_loading_bar(1.0)
        
        ratio = self.session._state.position / self._current_track.info.length
        return generate_loading_bar(ratio)

    @property
    def volume_bar(self):
        return generate_volume_bar(self.session._volume)
    
    @property
    def queue_contents(self):
        return self.session.dget_contents()

    @property
    def pos_timestamp(self):
        if self._completed is True:
            return self.len_timestamp
        return timestamp_from_ms(self.session._state.position)

    @property
    def len_timestamp(self):
        return timestamp_from_ms(self._current_track.info.length)
    
    def get_embed(self):
        description = f"`{self.pos_timestamp} {self.track_progress_bar} {self.len_timestamp}`\n\n"
        spaces = len(self.pos_timestamp) - 4
        description += f"`{spaces * ' '}Vol: {self.volume_bar} {self.session._volume}%`\n\n"
        description += f"```{self.queue_contents}```"

        embed = hikari.Embed(
            title=self._current_track.info.title,
            description=description
        )

        embed.set_thumbnail(self._current_track.info.artwork_url)
        embed.url = self._current_track.info.uri
        return embed

    def set_complete(self):
        self._completed = True
    
    async def stop(self):
        self._controls.stop()
        self._stopped = True
        await self.update()
    
    async def complete(self):
        self.set_complete()
        await self.stop()
        await self.update()
    
    async def begin(self):
        if self._message is not None:
            raise ValueError("begin() has already been called.")
        
        self._message = await self.session.send(
            embed=self.get_embed(),
            components=self._controls
        )
        await self._controls.start(self._message)
    
    async def update(self):
        if self._message is None:
            raise ValueError("begin() must be called first.")
        
        components = [] if self._stopped is True else self._controls
        await self._message.edit(content=self.get_embed(), components=components)


def update_player_embed(option: str):
    if option not in ["pre-call", "post-call"]:
        raise ValueError(f"Invalid option '{option}'. It must be either 'pre-call' or 'post-call'.")
    
    def inner(func):
        async def wrapper(self, *args, **kwargs):
            if self._player_embed is not None:
                if option == "pre-call":
                    await self._player_embed.update()
                    return await func(self, *args, **kwargs)
                else:
                    result = await func(self, *args, **kwargs)
                    await self._player_embed.update()
                    return result
            return await func(self, *args, **kwargs)
        return wrapper
    return inner
    


# class PlayerEmbed:
#     def __init__(self, session):
#         self.session = session
#         self.description = ""
#         self.title = "Connected"
#         self.msg = None
#         self.initial_state = True
    
#     async def generate(self):
#         embed = hikari.Embed(title=self.title, description=self.description)
#         return embed
    
#     async def dreset(self):
#         self.msg = None
#         await self.dupdate()
    
#     async def dupdate(self, complete=False):
#         embed = await self.generate()
        
#         if self.session._current_track is not None:
#             embed.title = self.session._current_track.info.title
            
#             if complete is True:
#                 ratio = 1.0
#             else:
#                 ratio = self.session._state.position / self.session._current_track.info.length
#             bar = generate_loading_bar(ratio)

#             post_pos = timestamp_from_ms(self.session._current_track.info.length)
#             if complete is True:
#                 pre_pos = post_pos
#             else:
#                 pre_pos = timestamp_from_ms(self.session._state.position)

#             if self.session._is_paused:
#                 self.description = f"`{pre_pos} {bar} {post_pos}`"
#             else:
#                 self.description = f"`{pre_pos} {bar} {post_pos}`"

#             spaces = len(pre_pos) - 4
#             self.description += f"\n\n`{' ' * spaces}Vol: {generate_volume_bar(self.session._volume)} {self.session._volume}%`"
#             self.description += "\n" + self.session.dget_contents()
#             if self.session._current_track.info.artwork_url is not None:
#                 embed.set_thumbnail(self.session._current_track.info.artwork_url)
#             embed.description = self.description
#             self.initial_state = False
#         else:
#             embed.title = f"Connected to <#{self.session.voice_id}>"
#             embed.description = "Pending"

#         if self.msg is None:
#             self.msg = await self.session.send(embed=embed)
#         else:
#             await self.msg.edit(embed=embed)

#     async def update(self, complete=False):
#         async with self.session.lock:
#             return await self.dupdate(complete=complete)