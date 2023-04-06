# Azura 4

Azura is a powerful Discord music bot with advanced features, and the ability to connect to more than one channel in the same server.


## How's she work?
First and foremost, I want to get one thing out there. **Azura is not a normal bot.** She doesn't operate the same way "normal" music bots do, and this is for reasons I will explain. Let's look first at how Azura came about, because that's integral to explaining why she's designed the way she is.

#### A Growing Server with a Growing Problem
When I first wrote Azura, I did so because I wanted a music bot that offered more complex functionality than what was available at the time. The ability to store and create playlists, or the ability to have global playlists. The ability to advance back and forth by specific numbers, or to particular parts of the queue. The ability to enqueue songs to the front of the queue, or the back, or to interlace songs with others. None of this existed at the time, and a lot of it, to be honest, still doesn't. So I wrote Azura. She went through some revisions, but at her core, she was one bot on one server.

Then my server got a bit bigger. We soon found ourselves in an increasingly familiar situation where we'd have multiple active voice channels who all want to use the music bot. Azura is one bot, who cannot connect to more than one channel. Problem.

The simple solution to this is to have more than one bot, but think about what Azura is, and what that means: since Azura stores playlists, this means both bots need to access the same database. The commands all need to be a perfect match, and they have to be kept in sync with each other.

I found a way to do this in what was, admittedly, a bodge. A massive, ugly bodge which effectively had me running two copies of Azura, both with different prefixes, but accessing the same database. We *tolerated* this for a while, and even then, with many mistakes resulting from people executing commands with the wrong prefix.

Then slash commands came.

So now you're telling me that not only would the commands be identical in prefix, but the user is expected to know and select the correct bot that's not being used from a list of them?

No. I draw the line there.

But what to do? It's clear that we can't simply have two bots with identical commands. That's way too messy, so let's not. Let's have one bot with one set of commands.
That's all fine and dandy, but now we have one bot who can only join one voice channel in one server at a time, so how do we fix that?
Multiple bots.

"What? But you just said..."

I know what I said. I never said both bots have to have commands. But if only one bot has commands, how does the second bot know what to do? Simple*. The first bot tells it what to do.

*Ah yes, the asterisk. That pesky symbol indicating that there's much more to the aforementioned information.
No, of course it's not simple, you idiot. We're talking about running two separate processes, and having these processes talk to each other somehow while also running a highly intricate queue system. How on earth do we do that?

This is the ambitious problem that Azura is meant to solve. The way she does this is with a custom session management system I wrote called "Koe". Koe is uniquely designed to manage voice sessions both locally and remotely.

#### Understanding Koe
The key to understanding how Azura works is understanding hoe *Koe* works. Koe effectively wraps Lavasnek_rs' session system, adding in extra functionality along the way.
At the top, there is the `Koe` object itself. Koe acts as the effective "business end" of the system, providing access to methods which allow one to create, destroy, and manipulate voice sessions. `Koe` stores these sessions in an internal dictionary mapping voice channel IDs to the session objects themselves.
The session objects stored within are one of two flavors, `LocalSession` and `RemoteSession`.

- `LocalSession` are instances of a voice connection which is local to the `Koe` instance containing it. A `LocalSession` has methods like `connect()`, `skip()`, `pause()`, etc... It operates pretty much exactly how you'd expect.
- `RemoteSession` are instances of a voice connection which is *not* local to the `Koe` instance containing it. Within the Koe architecture, these can really only be instantiated by the parent bot. They also contain the exact same methods as a `LocalSession`, except instead of calling the correct code directly, they map to web endpoints which when called, make requests to the child bot that the endpoint maps to.

So how's all this fit together?
When someone makes a request for a song to be played, the request is received by the parent bot, and ultimately passed to the bot's `Koe` instance. Koe then checks to see if an existing session for the voice channel requested exists. If it does, great! We can simply get that session, and then call `play()` on it. But if it doesn't then Koe needs to figure out if the parent is already connected to the guild in question. If the parent isn't, great! Koe creates an instance of `LocalSession`, and then calls the `connect()` method, to connect to the voice channel and begin playback. If the parent is already connected though, then that means someone is already using the parent in the server. So instead, Koe sets up the creation of a `RemoteSession`. It does this by first checking with the child bots to see if any are available for that guild. The parent will take the first one which is able to respond, if any. After a handshake of sorts, the parent creates an instance of `RemoteSession`, and then calls `connect()` on it. This causes a web request to be sent to the web server running on all of the bots, and then is received by the child. The child bot responds by invoking its own `Koe` instance, creating it's own `LocalSession`, ultimately calling the `connect()` method on it. This connects the child to the voice channel, and the request is complete. Now do this for every single command that can be executed, and bam. That's Koe.

This glosses over a bit. Like for example, the fact that when a session is disconnected, all instances matching that session have to be deleted, remote or otherwise. This is mostly fine since the parent bot handles almost all commands.

* ahem *. Almost.

See, you're forgetting about buttons, which - by their very nature - must be handled by the bot that sends the message. In the instance of a `RemoteSession`, this would be the child bot. But if the child bot disconnects their own `LocalSession`, then that means the parent bot has absolutely no idea what happened. To ensure uniformity, if the child bot is the one destroying the session, it must also make an upstream call to an endpoint on the parent, instructing it to delete the `RemoteSession` which corresponds to the local one they just deleted. Every little bit of this glosses over some complexity. But Koe is a complex system. I set high standards when I began solving these original problems, and Koe is the only system I know of that meets them.
