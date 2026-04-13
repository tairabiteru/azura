from django.urls import path

from .views import get_player, get_player_templ, update_player, upload_file, get_songs
from .views import playlists, get_playlist, save_playlist, delete_playlist


urlpatterns = [
    path("player", get_player),
    path("player-get", get_player_templ),
    path("player-update", update_player),
    path("get-songs", get_songs),
    path("upload", upload_file),
    path("playlists", playlists),
    path("get-playlist", get_playlist),
    path("save-playlist", save_playlist),
    path("delete-playlist", delete_playlist)
]
