#!/usr/bin/env python
"""Module defining the MVC management function

So this probably looks familiar, huh? Since there's no other file to write docstrings
in this directory, I'm just gonna write the general description here.

Azura's Model-View Controller *IS* Django, albeit a heavily modified version of it. I
have a weird mixture of feelings about the work I've done in here. Django is very, VERY
clearly not set up to work with something like the Discord API, at all. That is painfully
obvious when you read further into the work done in here, and realize that a lot of it
doesn't make a ton of sense. So with other web frameworks out there that work
thousands of times better, why did I choose to use Django?

Well, truthfully, it's the ORM. I love Django's ORM, and I love the migration tool
built into it. A framework like Sanic would work a lot better for the web end of this,
and in fact, that WAS what Azura used to use. However, Sanic is only one half of what
Django does. The other half being the ORM, which I'd have to engage a separate library
for.

"Wait, so you're telling me that process of using a separate library is *THAT* painful?"
YES. YES I AM.

The previous library I used, Tortoise, was among the only other asynchronous ORMs I found
which spoke to me in a way that made sense. Tortoise would have been perfect, except that
its migration tool, aerich, is horrible to deal with in a complex environment like this.
Credit where credit is due, aerich works fine for a lot of purposes, and it's developed
by volunteers in their free time. But when compared to Django's migration tool, it just
pales. Combine that with the fact that Django also offers an administrative interface
for interacting with objects in the database - literal WEEKS worth of work - just, for
free. No strings attached.

Yeah, sorry. Django wins. It is not perfect. Far from it, and I had to reverse engineer
a lot of Django to even get this to work, and I have doubts that what I wrote even makes
sense in a lot of cases. But the question ultimately boils down to this: "Am I more satisfied
with what I wrote here when compared to Tortoise?" And the answer, is "Yes. I am."

tl;dr, this is bad, I know. Leave me alone, I've made my decision, for better or for worse.

...Oh right! Should probably detail the contents of this file, huh?

    * main - Function implementing the behavior of this file when run via 'azura mvc'
"""


import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    print(sys.argv)
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
