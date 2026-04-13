"""f URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.conf import settings
from .views import index, auth, protected_file
from ...core.conf import Config


conf = Config.load()


favicon = RedirectView.as_view(url="/static/favicon.ico", permanent=True)


admin.site.site_header = f"{conf.name} Administration"


urlpatterns = [
    path("", index),
    path("auth/", auth),
    path("music/", include("azura.mvc.music.urls")),
    path("admin/", admin.site.urls),
    
    re_path('^uploads/cabinet/.+', protected_file, name='protected_file'),
    path('favicon.ico', favicon),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
