# Azura
Azura is a music bot created for my Discord server. She brings the good beats.

## Why?
There are many music bots out there, but none that do exactly what I want. Azura solves three problems I have with most music bots:

1. I want a rich built-in interface which I can use to interact with the player. I want pause buttons and volume buttons and stuff.
2. I want playlists. Sure, other bots let you pass in Youtube playlists, but I want more granularity and control than that.
3. I want a bot which can join multiple channels in the same server.

The last problem in particular, is completely impossible to solve. You cannot have a *single* bot that can join multiple voice channels in the same server for the same reason a member cannot join multiple voice channels in the same server.

That's why Azura doesn't do that. Instead, Azura is a bot written to do three things: play music, manage playlists, and *control other bots*. These other bots she controls allow her to effectively be in multiple channels in the same server. While the bot that joins is different, the commands are all the same.


## Nerd Stuff
Azura is powered by Hikari, Lightbulb, Lavasnek_rs, and a custom music framework which I've dubbed "Koe". Koe is effectively a voice session management system designed to work both with local and remote bots. Koe stores voice sessions as instances of `LocalKoeSession` and `RemoteKoeSession`. For the most part, the core methods of these classes are identical in name and parameters. They differ however in what's under the hood.

- A `LocalKoeSession` can only be initialized by the bot who's ultimately responsible for the playback and control of said session. The methods defined for it do exactly what you'd expect. (`connect()` connects, `disconnect()` disconnects, etc...)
- A `RemoteKoeSession` can only be initialized by the "master" bot. The methods don't actually do what they say though. Instead, they make `POST` requests to endpoints established by an internal webserver running on all bots. The master bot uses these endpoints to instruct the subordinate bots on what to do.

Commands passed into this system are all processed by the master bot. But the master bot processes them based on the type of session which is stored in Koe. The master bot is able to use endpoints to see the voice states of the subordinates, and use this information to decide which bot, if any, can connect to a voice channel and process playback requests.

Amazingly, this...works. (God, I can't believe this works...)
