from django.urls import path, re_path

from .views import comments, homepage, blogitem, blogitems, search, hydro


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
    # I prefer trailing / but because of how NextJS treats proxied XHR
    # requests, in the client-side, via localhost:3000 it forces it to be
    # sans trailing /. Not loving this.
    path("autocompete", search.autocompete, name="autocompete"),
    path("search_meilisearch", search.search_meilisearch, name="search_meilisearch"),
    re_path("search/?", search.search, name="search"),
    path("__hydro__", hydro.receive, name="hydro_receive"),
]
