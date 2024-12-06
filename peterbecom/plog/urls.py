from django.urls import path

from . import views

urlpatterns = [
    path("prepare.json", views.prepare_json, name="prepare"),
]
