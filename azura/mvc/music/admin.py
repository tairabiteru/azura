from django.contrib import admin
from .models import Playlist, PlaylistEntry, PlaybackHistoryEntry
    

admin.site.register(Playlist)
admin.site.register(PlaylistEntry)
admin.site.register(PlaybackHistoryEntry)