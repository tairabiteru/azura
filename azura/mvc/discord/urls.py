from django.urls import path
from .views import user, save_user

urlpatterns = [
    path("user", user),
    path("user/save", save_user)
]
