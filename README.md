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
Azura is powered by Hikari, Lightbulb, Lavasnek_rs, and a custom music framework which I've dubbed "Koe". Koe is effectively a voice session management system designed to work both with local and remote bots. Koe stores voice sessions as instances of `LocalKoeSession`, `RemoteKoeSession`, and `ChildKoeSession`. For the most part, the core methods of these classes are identical in name and parameters. They differ however in what's under the hood.

- A `LocalKoeSession` can only be initialized by the parent bot. It represents a session wherein the parent bot is the one connecting and initiating playback. The methods defined for it do exactly what you'd expect. (`connect()` connects, `disconnect()` disconnects, etc...)
- A `RemoteKoeSession` can only be initialized by the parent bot. The methods don't actually do what they say though. Instead, they make `POST` requests to endpoints established by an internal webserver running on all bots. The parent bot uses these endpoints to instruct the child bots on what to do.
- A `ChildKoeSession` can only be initialized by child bots. They are created when a `RemoteKoeSession` is initialized by the parent bot, and then connected. The web request made by the `connect()` method spawns an instance of `ChildKoeSession` on the bot which is to handle the request. A `ChildKoeSession` is nearly identical to a `LocalKoeSession`. (In fact it inherits from it.) The only difference is in the `disconnect()` method. Since the disconnect may come from a button press and not a command, a disconnect also needs to inform the parent bot of the session closure.

Commands passed into this system are all processed by the parent bot. But the parent bot processes them based on the type of session which is stored in Koe. The parent bot is able to use endpoints to see the voice states of the children, and use this information to decide which bot, if any, can connect to a voice channel and process playback requests.

Amazingly, this...works. (God, I can't believe this works...)

This is the underlying theory of operation behind Azura. The parent bot handles all slash commands. Those commands, if necessary, are passed on to a child bot if the parent is already busy. The child bots handle their own playback messages, as well as the buttons attached to those messages. Most of the communication between the bots is unidirectional, with the parent bot making requests, and the child bots simply responding in acknowledgement. The only exception to this is when a disconnect happens via a button press, wherein the child bot must inform the parent to maintain a valid state of sessions.

In short, "How does Azura work?"

I've got absolutely no idea. Probably magic.
