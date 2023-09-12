from django.urls import path
from .views import playlists, playlist_get, playlist_delete, playlist_save

urlpatterns = [
    path("", playlists),
    path("get/", playlist_get),
    path("delete/", playlist_delete),
    path("save/", playlist_save),
]
