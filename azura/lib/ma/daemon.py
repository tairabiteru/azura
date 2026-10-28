from __future__ import annotations

import hashlib

import hikari
import koe
import music_assistant_client as ma


class MAStreamEmbed(hikari.Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hash: str | None = None

    @property
    def hash(self) -> str:
        if not self._hash:
            raise RuntimeError("hash not set")
        return self._hash

    @classmethod
    def from_event_data(cls, data: dict) -> MAStreamEmbed:
        embed = cls(title="Now Playing")
        embed.set_thumbnail(data["current_media"]["image_url"])
        embed.add_field(name="Title", value=data["current_media"]["title"])
        embed.add_field(name="Artist", value=data["current_media"]["artist"])
        hashstr = data["current_media"]["title"] + data["current_media"]["artist"]
        embed._hash = hashlib.sha256(hashstr.encode()).hexdigest()
        return embed


class MADaemon:
    _last_writes: dict[str, str] = {}

    def __init__(self, bot: hikari.GatewayBot):
        self.bot = bot
        self.loop = hikari.internal.aio.get_or_make_loop()  # pyright: ignore[reportAttributeAccessIssue]

    async def on_event(self, event: ma.client.MassEvent) -> None:
        if event.event == ma.client.EventType.PLAYER_UPDATED:
            if event.data["name"] == self.bot.conf.ma.player_name:
                await self.handle_koe(event.data)

    async def handle_koe(self, data: dict) -> None:
        if data["device_info"]["model"] != "SqueezeLite":
            return

        koe: koe.Koe = self.bot.koe
        sessions: list[koe.Session] = []
        for session in koe._sessions.values():
            if session._current_track is not None:
                if (
                    data["device_info"]["ip_address"]
                    in session._current_track.info.identifier
                ):
                    sessions.append(session)

        for session in sessions:
            if session.channel_id is not None:
                embed = MAStreamEmbed.from_event_data(data)

                if session._id in self._last_writes:
                    if self._last_writes[session._id] == embed.hash:
                        return

                await self.bot.rest.create_message(session.channel_id, embed=embed)
                self._last_writes[session._id] = embed.hash

    async def proc(self) -> None:
        async with ma.MusicAssistantClient(
            self.bot.conf.ma.api_url,
            None,
            token=self.bot.conf.ma.token,  # pyright: ignore[reportAttributeAccessIssue]
        ) as client:
            client.subscribe(self.on_event)

            await client.start_listening()

    @classmethod
    async def run(cls, bot: hikari.GatewayBot) -> MADaemon:
        inst = cls(bot)
        inst.loop.create_task(inst.proc())
        return inst
