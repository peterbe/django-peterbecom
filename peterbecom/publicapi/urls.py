from django.urls import path

from . import views


app_name = "publicapi"

urlpatterns = [
    path("plog/<slug:oid>", views.blogpost, name="blogpost"),
    path("plog/", views.blogitems, name="blogitems"),
]
