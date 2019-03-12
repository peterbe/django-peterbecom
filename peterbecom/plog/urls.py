from django.conf.urls import url

from . import views


urlpatterns = [
    url("^$", views.plog_index, name="plog_index"),
    url("^calendar/$", views.calendar, name="calendar"),
    url("^calendar/data/$", views.calendar_data, name="calendar_data"),
    url("^new-comments$", views.new_comments, name="new_comments"),
    url("^prepare.json$", views.prepare_json, name="prepare"),
    url("^preview.json$", views.preview_json, name="preview"),
    url("^hits$", views.plog_hits, name="plog_hits"),
    url("^hits/data$", views.plog_hits_data, name="plog_hits_data"),
    url("^(.*)/submit$", views.submit_json, name="submit"),
    url(
        "^(.*)/all-comments$",
        views.all_blog_post_comments,
        name="all_plog_post_comments",
    ),
    url("^screenshot/(.*)", views.blog_screenshot, name="blog_screenshot"),
    url(r"^(.*)/ping$", views.blog_post_ping, name="blog_post_ping"),
    url("^(.*)/awspa$", views.blog_post_awspa, name="blog_post_awspa"),
    url("^(.*)", views.blog_post, name="blog_post"),
]
