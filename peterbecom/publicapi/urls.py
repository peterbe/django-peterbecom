from django.urls import path

from . import views


app_name = "publicapi"

urlpatterns = [
    path(
        "plog/comments/prepare",
        views.prepare_comment,
        name="prepare_comment",
    ),
    path(
        "plog/comments/preview",
        views.preview_comment,
        name="preview_comment",
    ),
    path(
        "plog/comments/submit",
        views.submit_comment,
        name="submit_comment",
    ),
    path("plog/homepage", views.homepage_blogitems, name="homepage_blogitems"),
    path("plog/<str:oid>", views.blogpost, name="blogpost"),
    path("plog/", views.blogitems, name="blogitems"),
    path("search/", views.search, name="search"),
]
