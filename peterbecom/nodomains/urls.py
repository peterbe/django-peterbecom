from django.conf.urls import url

from . import views


app_name = "nodomains"

urlpatterns = [
    url("^$", views.index, name="index"),
    url("^histogram$", views.histogram, name="histogram"),
]
