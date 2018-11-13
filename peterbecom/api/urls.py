from django.conf.urls import url

from . import views


app_name = "api"

urlpatterns = [
    url("^plog/$", views.blogitems, name="blogitems"),
    url("^plog/preview/$", views.preview, name="preview"),
    url(
        "^plog/(.*)/open-graph-image$", views.open_graph_image, name="open_graph_image"
    ),
    url("^plog/(.*)$", views.blogitem, name="blogitem"),
    url("^categories/?$", views.categories, name="categories"),
    url("", views.catch_all, name="catch_all"),
]
