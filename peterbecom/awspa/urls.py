from django.urls import path

from . import views


app_name = "awspa"

urlpatterns = [
    path("keywords", views.all_keywords, name="all_keywords"),
    path("delete", views.delete_awsproduct, name="delete_awsproduct"),
    path("archive", views.plog_archive, name="plog_archive"),
]
