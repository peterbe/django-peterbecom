from django.urls import path, re_path

from . import views


app_name = "chiveproxy"

urlpatterns = [
    path("api/cards/", views.api_cards, name="api_cards"),
    re_path(r"api/cards/(?P<pk>\d+)/", views.api_card, name="api_card"),
]
