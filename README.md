# Elysia
A Discord bot that nags you to do chores.

I'm bad at remembering things because like many of my friends, I have been known to display a lack of [✨executive function!✨](https://en.wikipedia.org/wiki/Autism) So what is one to do? Why, write a bot that nags you into doing things of course!

Elysia is equipped to implement two primary concepts at the moment:
1. **Reminders** - A reminder is a thing you want to be reminded of. A reminder has some rule by which its futures are determined, and a piece of text which helps to remind you. The idea then, is that given some text and a future rule like "at 12:30", when the clock strikes 12:30, you'll be sent that text. Reminders can also optionally recur.
2. **Chores** - Chores are recurring things to be reminded of. Unlike a reminder, they are always recurring, and have some future rule which dictates how often they occur. Additionally, unlike a reminder, the *accomplishment* of a chore is tracked, and thusly, Elysia knows how often you're doing them, and when they should be done next.

Eventually I plan to add more, but for now, these two concepts are helpful to me.
Elysia accomplishes these two goals with the use of a scheduling library I wrote called [Oronyx](https://github.com/tairabiteru/oronyx).

# FAQ
- Did you procrastinate doing chores while writing this?
    - Yes, of course I did. You honestly had to ask?
- What's the name mean?
    - She's named after [Elysia](https://honkaiimpact3.fandom.com/wiki/Elysia).