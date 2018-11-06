from django.conf.urls import url

from . import views


app_name = "api"

urlpatterns = [
    url("^plog/$", views.blogitems, name="blogitems"),
    url("^categories/?$", views.categories, name="categories"),
]
