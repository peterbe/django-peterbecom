from django.conf.urls import url

from . import views


urlpatterns = [
    url("^$", views.plog_index, name="plog_index"),
    url("^edit/(.*)", views.edit_post, name="edit_post"),
    url("^awspa/(.*)", views.plog_awspa, name="plog_awspa"),
    url(
        "^open-graph-image/(.*)",
        views.plog_open_graph_image,
        name="plog_open_graph_image",
    ),
    url(
        "^thumbnails/delete/(?P<pk>\d+)$",
        views.delete_post_thumbnail,
        name="delete_post_thumbnail",
    ),
    url("^thumbnails/(.*)", views.post_thumbnails, name="post_thumbnails"),
    url("^calendar/$", views.calendar, name="calendar"),
    url("^calendar/data/$", views.calendar_data, name="calendar_data"),
    url("^add/$", views.add_post, name="add_post"),
    url("^add/file/$", views.add_file, name="plog_add_file"),
    url("^preview$", views.preview_post, name="plog_preview_post"),
    url("^new-comments$", views.new_comments, name="new_comments"),
    url("^prepare.json$", views.prepare_json, name="prepare"),
    url("^preview.json$", views.preview_json, name="preview"),
    # url('^inbound-email$', views.inbound_email, name='inbound_email'),
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
