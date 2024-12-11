from django.urls import path, re_path

from .views import (
    blogitem,
    blogitems,
    comments,
    events,
    homepage,
    hydro,
    lyrics,
    search,
)

app_name = "publicapi"

urlpatterns = [
    path(
        "plog/comments/prepare",
        comments.prepare_comment,
        name="prepare_comment",
    ),
    path(
        "plog/comments/preview",
        comments.preview_comment,
        name="preview_comment",
    ),
    path(
        "plog/comments/submit",
        comments.submit_comment,
        name="submit_comment",
    ),
    path("plog/homepage", homepage.homepage_blogitems, name="homepage_blogitems"),
    path("plog/<str:oid>", blogitem.blogitem, name="blogitem"),
    path("plog/", blogitems.blogitems, name="blogitems"),
    path("typeahead", search.typeahead, name="typeahead"),
    path("lyrics/search", lyrics.search, name="lyrics_search"),
    path("lyrics/song", lyrics.song, name="lyrics_song"),
    path("lyrics/featureflag", lyrics.feature_flag, name="lyrics_feature_flag"),
    re_path("search/?", search.search, name="search"),
    path("__hydro__", hydro.receive, name="hydro_receive"),
    path("events", events.event, name="events_event"),
]
