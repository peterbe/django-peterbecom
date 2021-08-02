from django.urls import re_path

from . import views


app_name = "localvsxhr"

urlpatterns = [
    re_path("^$", views.index, name="index"),
    re_path("^stats$", views.stats, name="stats"),
    re_path("^download.json$", views.download_json, name="download_json"),
    re_path("^store$", views.store, name="store"),
    re_path("^store/boot$", views.store_boot, name="store_boot"),
    re_path("^localforage.html$", views.localforage, name="localforage"),
    re_path(
        "^localforage-localstorage.html$",
        views.localforage_localstorage,
        name="localforage_localstorage",
    ),
    re_path("^localstorage.html$", views.localstorage, name="localstorage"),
]
