from django.urls import path

from .views import comments, homepage, blogpost, blogposts, search


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
    path("plog/<str:oid>", blogpost.blogpost, name="blogpost"),
    path("plog/", blogposts.blogitems, name="blogitems"),
    path("search/", search.search, name="search"),
]
