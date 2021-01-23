from django.urls import path

from . import views


app_name = "chiveproxy"

urlpatterns = [
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:pk>/", views.api_card, name="api_card"),
    path("card/<int:pk>", views.card, name="card"),
    path("", views.home, name="home"),
    path("search", views.home, name="home_search"),
]
