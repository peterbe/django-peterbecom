from django import http
from django.urls import path

from . import views

app_name = "chiveproxy"


def append_slash(request, *args, **kwargs):
    return http.HttpResponseRedirect(f"{request.get_full_path()}/")


urlpatterns = [
    path("api/cards", append_slash),
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:pk>", append_slash),
    path("api/cards/<int:pk>/", views.api_card, name="api_card"),
    path("api/imageproxy", views.image_proxy, name="image_proxy"),
]
