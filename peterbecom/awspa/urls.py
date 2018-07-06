from django.conf.urls import url

from . import views


app_name = "awspa"

urlpatterns = [
    url("^keywords$", views.all_keywords, name="all_keywords"),
    url("^delete$", views.delete_awsproduct, name="delete_awsproduct"),
    url("^archive$", views.plog_archive, name="plog_archive"),
]
