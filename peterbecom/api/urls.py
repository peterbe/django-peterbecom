from django.urls import path, re_path

from . import analytics, classification, spam, views

app_name = "api"

urlpatterns = [
    path("plog/", views.blogitems, name="blogitems"),
    path("plog/hits/", views.blogitem_hits, name="blogitem_hits"),
    path(
        "plog/realtimehits/",
        views.blogitem_realtimehits,
        name="blogitem_realtimehits",
    ),
    path(
        "plog/spam/patterns",
        spam.patterns,
        name="spam_patterns",
    ),
    path("plog/spam/signatures", spam.signatures, name="spam_signatures"),
    path("plog/comments/geo/", views.geocomments, name="geocomments"),
    path(
        "plog/comments/<str:oid>/classify/",
        classification.comment_classify,
        name="comment_classify",
    ),
    path(
        "plog/comments/counts/",
        views.comment_counts,
        name="comment_counts",
    ),
    path(
        "plog/comments/auto-approved-records/",
        views.comment_auto_approved_records,
        name="comment_auto_approved_records",
    ),
    path("plog/comments/", views.blogcomments, name="blogcomments"),
    re_path(
        r"^plog/comments/(?P<action>approve|delete|both)/$",
        views.blogcomments_batch,
        name="blogcomments_batch",
    ),
    path("plog/preview/", views.preview, name="preview"),
    re_path(r"^plog/(.*)/images$", views.images, name="images"),
    re_path(r"^plog/(.*)/hits$", views.hits, name="hits"),
    re_path(
        r"^plog/(.*)/open-graph-image$", views.open_graph_image, name="open_graph_image"
    ),
    re_path(r"^plog/(.*)$", views.blogitem, name="blogitem"),
    path("categories", views.categories, name="categories"),
    path("postprocessings/", views.postprocessings, name="postprocessings"),
    path("searchresults/", views.searchresults, name="searchresults"),
    path("cdn/check", views.cdn_check, name="cdn_check"),
    path("cdn/config", views.cdn_config, name="cdn_config"),
    path(
        "cdn/purge/urls/count",
        views.cdn_purge_urls_count,
        name="cdn_purge_urls_count",
    ),
    path("cdn/purge/urls", views.cdn_purge_urls, name="cdn_purge_urls"),
    path("cdn/purge", views.cdn_purge, name="cdn_purge"),
    path("cdn/probe", views.cdn_probe, name="cdn_probe"),
    path(
        "lyrics-page-healthcheck",
        views.lyrics_page_healthcheck,
        name="lyrics_page_healthcheck",
    ),
    path("xcache/analyze", views.xcache_analyze, name="xcache_analyze"),
    path("whereami", views.whereami, name="whereami"),
    path("whoami", views.whoami, name="whoami"),
    path("__healthcheck__", views.healthcheck, name="healthcheck"),
    path("analytics/query", analytics.query, name="analytics_query"),
    path("", views.catch_all, name="catch_all"),
]
