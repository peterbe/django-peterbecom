from django import http
from django.urls import path, re_path

from . import views


urlpatterns = [
    path(r"", views.plog_index, name="plog_index"),
    path("calendar", views.calendar, name="calendar"),
    path("calendar/data/", views.calendar_data, name="calendar_data"),
    path("new-comments", views.new_comments, name="new_comments"),
    path("prepare.json", views.prepare_json, name="prepare"),
    path("preview.json", views.preview_json, name="preview"),
    re_path(r"^(.*)/submit$", views.submit_json, name="submit"),
    re_path(
        "^(.*)/all-comments$",
        views.all_blog_post_comments,
        name="all_plog_post_comments",
    ),
    re_path(r"^screenshot/(.*)", views.blog_screenshot, name="blog_screenshot"),
    re_path(
        r"^(?P<oid>.*)/p(?P<page>\d+)/ping$",
        views.blog_post_ping,
        name="blog_post_ping",
    ),
    re_path(r"^(?P<oid>.*)/ping$", views.blog_post_ping, name="blog_post_ping"),
    re_path(
        r"^(?P<oid>.*)/p(?P<page>\d+)/$",
        lambda r, oid, page: http.HttpResponseRedirect("/{}/p{}".format(oid, page)),
    ),
    re_path(r"^(?P<oid>.*)/p(?P<page>\d+)$", views.blog_post, name="blog_post"),
    re_path(r"^(?P<oid>.*)", views.blog_post, name="blog_post"),
]
