from django import http
from django.conf.urls import url

from . import views


urlpatterns = [
    url(r"^$", views.plog_index, name="plog_index"),
    url(r"^calendar/$", views.calendar, name="calendar"),
    url(r"^calendar/data/$", views.calendar_data, name="calendar_data"),
    url(r"^new-comments$", views.new_comments, name="new_comments"),
    url(r"^prepare.json$", views.prepare_json, name="prepare"),
    url(r"^preview.json$", views.preview_json, name="preview"),
    url(r"^hits$", views.plog_hits, name="plog_hits"),
    url(r"^hits/data$", views.plog_hits_data, name="plog_hits_data"),
    url(r"^(.*)/submit$", views.submit_json, name="submit"),
    url(
        "^(.*)/all-comments$",
        views.all_blog_post_comments,
        name="all_plog_post_comments",
    ),
    url(r"^screenshot/(.*)", views.blog_screenshot, name="blog_screenshot"),
    url(
        r"^(?P<oid>.*)/p(?P<page>\d+)/ping$",
        views.blog_post_ping,
        name="blog_post_ping",
    ),
    url(r"^(?P<oid>.*)/ping$", views.blog_post_ping, name="blog_post_ping"),
    url(
        r"^(?P<oid>.*)/p(?P<page>\d+)/awspa$",
        views.blog_post_awspa,
        name="blog_post_awspa",
    ),
    url(r"^(?P<oid>.*)/awspa$", views.blog_post_awspa, name="blog_post_awspa"),
    url(
        r"^(?P<oid>.*)/p(?P<page>\d+)/$",
        lambda r, oid, page: http.HttpResponseRedirect("/{}/p{}".format(oid, page)),
    ),
    url(r"^(?P<oid>.*)/p(?P<page>\d+)$", views.blog_post, name="blog_post"),
    url(r"^(?P<oid>.*)", views.blog_post, name="blog_post"),
]
