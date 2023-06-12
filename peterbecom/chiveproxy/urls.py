from django.urls import path

from . import views


app_name = "chiveproxy"

urlpatterns = [
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:pk>/", views.api_card, name="api_card"),
]
