from django.urls import path

from . import views

app_name = "minimalcss"

urlpatterns = [path("minimize", views.minimize, name="minimize")]
