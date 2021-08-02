from django.urls import path

from . import views


app_name = "cdnthis"

urlpatterns = [
    path("", views.index, name="index"),
    path("nocaching/", views.nocaching, name="nocaching"),
    path("cached/", views.cached, name="cached"),
]
