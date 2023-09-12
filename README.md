# Azura 5
Azura is a powerful, fully featured music bot with playlist functionality, advanced track queueing, and a whole lot more.

## Why?
Azura was written at a time when advanced features like playlist support, advanced queues with the ability to move back and forth, skip to different spots, and dequeue were not available. Many of these features still aren't available, and so Azura remains. Plus, where's the fun in using some pre-made solution?

## Libraries and Software
Azura is written in Python 3, making use of [Hikari](https://github.com/hikari-py/hikari) for her API connection, and [Django](https://github.com/django/django) for her Model-View Controller. Her audio system, like many before her, is founded upon [Lavalink](https://github.com/lavalink-devs/Lavalink), and is specifically built for v4.

Notably missing from that list is any Python library for her Lavalink connection. That's because she doesn't have one. Azura interfaces directly with Lavalink via a component of her internally called "Hanabi", though I will note that Hanabi was very much inspired by [Lavaplay](https://github.com/HazemMeqdad/lavaplay.py) and [lavasnek_rs](https://github.com/vicky5124/lavasnek_rs). (You guys rock!)

## How Does Hanabi Work?
Alright, buckle up. I'm gonna try to explain it, but I barely get it myself, and I wrote the damn thing.

Hanabi is founded on the concept of a "session" or, an instance of a bot being connected to a voice channel. When you run a command which requires a voice connection, Azura's first objective is to obtain a session object from Hanabi. This session object may be either a 'local' or a 'remote' variety, but the methods it contains for acting upon a voice connection are the same between the two. A local session's methods directly act upon a voice connection in the way you'd expect. A remote variant as stated contains the same methods, but these methods instead act by transmitting information over a websocket connection to the child who is actually in control of the session. On the child's end, a remote session on the parent acts as a link to a local session on the child, and by interpreting the information recieved over the websocket, the child can receive direct instructions from the parent.

So basically, a local session is when the parent is in control. A remote session is when the parent is telling a child what to do on their behalf.

Previous iterations of Azura did this in the exact same manner, but instead of websockets, a REST API was used. Websockets require a lot less overhead in that each bot does not have to run an entire webserver. Further, the websocket connection can be kept open, and the result is much faster communication.

## FAQ
- **Why doesn't Azura use an existing Lavalink library?** - A lot of complicated reasons. The main one however, is that all previous versions of Azura "danced" around existing "oddities" in previous libraries she's used. (Not really oddities so much as differences in what they expect vs how Azura functions.) This isn't the maintainers' fault or anything, it's just that Azura's doing way more intricate queue management. I found that I was basically re-implementing what they'd already written, only differently. The only things my code didn't implement were the REST API calls and the websocket connection, and when I realized that I could do that myself, there was little point to continuing to use existing libraries like this.

- **Wait, so why is Hanabi different from a normal lavalink wrapper?** - There's two main reasons. First of all, Azura's queue management is a lot more intricate than most. Not only does Azura do the traditional stuff like appending to a queue, but she can also insert into the queue, interweave two playlists into one queue, and even dequeue items based on a rule. The second reason is because Azura is a *mutliplicity* of bots. She runs as a single bot, but allows you to configure more bots as her "children" who she can command, thus allowing her to operate in more than one voice channel in a single server. It is this basic requirement that explains her entire session system really. Azura doesn't simply respond to commands right off the bat because those commands *might not even be for her.*

- **How do Azura's children work without their own slash commands?** - The simple answer? They don't. Azura tells them what to do. The longer answer is that each bot, parent or child, is programmed to start a websocket server on a different port. When Azura initializes, she uses multiprocessing to also start her own children. Her children are programmed to send her a message saying they've completed initialization once this is done. From there, an open websocket connection is maintained with each child, and when commands are processed, Azura uses these connections to transmit information down the line, if need be.

- **Hanabi sounds kind of cool. Would you ever release it standalone?** - Probably not, gonna be honest. Hanabi is so specialized both to Hikari and Azura that I doubt anyone would have much use for it. Doing so would also restrict the way I want to use it with Azura and ultimately take more of my already limited time. If you want to pick through it though and see how it works, you're of course more than welcome.

- **There's a lot of stuff in your code that doesn't make sense.** - Yep. You think I understand any of this? All I did was write Azura...that doesn't mean I understand her. In seriousness, yes. I know. Azura v5 was a complete rewrite of her former self, and a lot of the design decisions have yet to be refined. At the same time, bear in mind that Azura's multi-bot nature forces her to work a bit differently compared to most music bots.

- **Can I add Azura to my Discord server?** - You're welcome to run her yourself, but if you're asking whether or not you can add *MY* instance of her, then the answer is no. I'm more than happy to share my code with others. Indeed, Azura would not exist without the kindness of strangers on the internet who decide to show others what they've done out of the kindness of their hearts. But my server has a finite amount of RAM. Go get your own.

- **Why does Azura use Django?** - Ugh...read the docstring in `azura/mvc/manage.py`. That explains it.