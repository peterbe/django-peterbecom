from django.conf.urls import url

from . import views


app_name = "api"

urlpatterns = [
    url("^plog/$", views.blogitems, name="blogitems"),
    url("^plog/hits/$", views.blogitem_hits, name="blogitem_hits"),
    url("^plog/comments/$", views.blogcomments, name="blogcomments"),
    url(
        "^plog/comments/(?P<action>approve|delete)/$",
        views.blogcomments_batch,
        name="blogcomments_batch",
    ),
    url("^plog/preview/$", views.preview, name="preview"),
    url("^plog/(.*)/images$", views.images, name="images"),
    url(
        "^plog/(.*)/open-graph-image$", views.open_graph_image, name="open_graph_image"
    ),
    url("^plog/(.*)$", views.blogitem, name="blogitem"),
    url("^categories/?$", views.categories, name="categories"),
    url("^postprocessings/", views.postprocessings, name="postprocessings"),
    url("^searchresults/", views.searchresults, name="searchresults"),
    url("", views.catch_all, name="catch_all"),
]
