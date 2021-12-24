from django.urls import path, re_path
from django.views.decorators.cache import cache_control
from .feed import PlogFeed
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("p<int:page>", views.home, name="home_paged"),
    re_path(
        r"(.*?)/?rss\.xml$", cache_control(public=True, max_age=60 * 60 * 6)(PlogFeed())
    ),
    path("search", views.search, name="search"),
    path("autocompete/v1", views.autocompete, name="autocompete"),
    path("about", views.about, name="about"),
    path("contact", views.contact, name="contact"),
    re_path(r"^oc-(?P<oc>.*)/p(?P<page>\d+)$", views.home, name="only_category_paged"),
    re_path(r"^oc-(?P<oc>.*)", views.home, name="only_category"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("humans.txt", views.humans_txt, name="humans_txt"),
    re_path(r"^slowstatic/(?P<path>.*)", views.slow_static, name="slow_static"),
    path("avatar.html", views.avatar_image_test_page, name="avatar_image_test_page"),
    re_path(
        r"avatar\.(?P<seed>\w+)\.png",
        views.avatar_image,
        name="avatar_image_seed",
    ),
    path("avatar.png", views.avatar_image, name="avatar_image"),
    path("__huey__", views.huey_test, name="huey_test"),
    path("__dynamic__", views.dynamic_page, name="dynamic_page"),
    path("__500__", views.preview_500, name="preview_500"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    re_path(r"^(.*)", views.catchall, name="catchall"),
]
