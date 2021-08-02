from django.urls import re_path

from . import views


app_name = "podcasttime"

urlpatterns = [
    re_path("^$", views.index, name="index"),
    re_path("^podcasts/$", views.legacy_podcasts, name="podcasts"),
    re_path("^podcasts/data/$", views.podcasts_data, name="podcasts_data"),
    re_path("^podcasts/table/$", views.podcasts_table, name="podcasts_table"),
    re_path("^picks/$", views.legacy_picks, name="picks"),
    re_path("^picks/data/$", views.picks_data, name="picks_data"),
    re_path("^find$", views.find, name="find"),
    re_path("^stats$", views.stats, name="stats"),
    re_path("^stats/episodes$", views.stats_episodes, name="stats_episodes"),
    re_path("^picked$", views.picked, name="picked"),
    re_path(
        r"^podcasts/episodes/(?P<id>\d+)$",
        views.podcast_episodes,
        name="podcast_episodes",
    ),
    re_path("^general-stats/(numbers)$", views.general_stats, name="general_stats"),
]
