from django.contrib import admin

from .models import Artist, Library, Playlist, Song, Stream

admin.site.register(Library)
admin.site.register(Artist)
admin.site.register(Song)
admin.site.register(Playlist)
admin.site.register(Stream)
