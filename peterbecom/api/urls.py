from django.conf.urls import url

from . import views


app_name = "api"

urlpatterns = [
    url(r"^plog/$", views.blogitems, name="blogitems"),
    url(r"^plog/hits/$", views.blogitem_hits, name="blogitem_hits"),
    url(
        r"^plog/realtimehits/$",
        views.blogitem_realtimehits,
        name="blogitem_realtimehits",
    ),
    url(r"^plog/comments/$", views.blogcomments, name="blogcomments"),
    url(
        r"^plog/comments/(?P<action>approve|delete)/$",
        views.blogcomments_batch,
        name="blogcomments_batch",
    ),
    url(r"^plog/preview/$", views.preview, name="preview"),
    url(r"^plog/(.*)/images$", views.images, name="images"),
    url(r"^plog/(.*)/hits$", views.hits, name="hits"),
    url(
        r"^plog/(.*)/open-graph-image$", views.open_graph_image, name="open_graph_image"
    ),
    url(r"^plog/(.*)/awspa$", views.awspa, name="awspa"),
    url(r"^plog/(.*)$", views.blogitem, name="blogitem"),
    url(r"^categories/?$", views.categories, name="categories"),
    url(r"^postprocessings/", views.postprocessings, name="postprocessings"),
    url(r"^searchresults/", views.searchresults, name="searchresults"),
    url(r"", views.catch_all, name="catch_all"),
]
