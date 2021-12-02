from core.conf import conf
from ext.koe.objects import NowPlayingMessage, Repeat
from ext.koe.queue import PositionError


class KoeEventHandler:
    def __init__(self, bot, *args, **kwargs):
        self.bot = bot

    async def player_update(self, lavalink, event):
        session = await self.bot.koe.fromGuild(event.guild_id)

        if session is not None:
            if session.now_playing_message is not None:
                await session.now_playing_message.update(event=event)

    async def track_start(self, lavalink, event):
        node = await lavalink.get_guild_node(event.guild_id)
        session = await self.bot.koe.fromGuild(event.guild_id)

        if node.now_playing is not None and session is not None:
            await session.setState("Playing")
            session.now_playing_message = NowPlayingMessage(session)

        await session.now_playing_message.generate()

        conf.logger.debug(f"Track started in guild: {event.guild_id}.")

    async def track_finish(self, lavalink, event):
        session = await self.bot.koe.fromGuild(event.guild_id)

        if session is not None:
            await session.setState("Finished")
            if session.now_playing_message is not None:
                if (await session.now_playing_message.isValid()):
                    await session.now_playing_message.close()

            mode = await session.repeatMode()
            if mode == Repeat.ONE:
                track = await session.queue.currentTrack()
                await session.bot.lavalink.play(session.gid, track.track).requester(track.requester).start()
            elif event.reason not in ["REPLACED", "STOPPED"]:
                try:
                    await session.queue.move(1)
                    track = await session.queue.currentTrack()
                    await session.bot.lavalink.play(session.gid, track.track).requester(track.requester).start()
                except PositionError:
                    if mode == Repeat.ALL:
                        await session.queue.set_pos(0)
                        track = await session.queue.currentTrack()
                        await session.bot.lavalink.play(session.gid, track.track).requester(track.requester).start()

            await session.overwriteNode()
        conf.logger.debug(f"Track finished in guild: {event.guild_id}.")

    async def track_exception(self, lavalink, event):
        conf.logger.warning(f"Track exception happened in guild: {event.guild_id}.")

        skip = await lavalink.skip(event.guild_id)
        node = await lavalink.get_guild_node(event.guild_id)

        if not skip:
            await event.message.respond("Nothing to skip")
        else:
            if not node.queue and not node.now_playing:
                await lavalink.stop(event.guild_id)
