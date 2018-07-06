from django.conf.urls import url

from . import views


app_name = "minimalcss"

urlpatterns = [url("^minimize", views.minimize, name="minimize")]
