from django import http
from django.urls import path, re_path

from . import views

urlpatterns = [
    path(r"", views.plog_index, name="plog_index"),
    path("prepare.json", views.prepare_json, name="prepare"),
    path("preview.json", views.preview_json, name="preview"),
    re_path(r"^(.*)/submit$", views.submit_json, name="submit"),
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
