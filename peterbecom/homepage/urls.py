from django.http import HttpResponsePermanentRedirect
from django.conf.urls import url
from django.views.decorators.cache import cache_control
from .feed import PlogFeed
from . import views


urlpatterns = [
    url("^$", views.home, name="home"),
    url(r"^p(?P<page>\d+)$", views.home, name="home_paged"),
    url(
        r"(.*?)/?rss\.xml$", cache_control(public=True, max_age=60 * 60 * 6)(PlogFeed())
    ),
    url("^search$", views.search, name="search"),
    url("^autocompete/v1$", views.autocompete, name="autocompete"),
    url("^About$", lambda x: HttpResponsePermanentRedirect("/about/")),
    url("^about$", views.about, name="about"),
    url("^contact$", views.contact, name="contact"),
    url(r"^oc-(?P<oc>.*)/p(?P<page>\d+)$", views.home, name="only_category_paged"),
    url(r"^oc-(?P<oc>.*)", views.home, name="only_category"),
    url("^zitemap.xml$", lambda x: HttpResponsePermanentRedirect("/sitemap.xml")),
    url("^sitemap.xml$", views.sitemap, name="sitemap"),
    url("^humans.txt$", views.humans_txt, name="humans_txt"),
    url(r"^slowstatic/(?P<path>.*)", views.slow_static, name="slow_static"),
    url(r"avatar\.html", views.avatar_image_test_page, name="avatar_image_test_page"),
    url(
        r"avatar\.(?P<seed>\w+)\.png",
        views.avatar_image,
        name="avatar_image",
    ),
    url(r"avatar\.png", views.avatar_image, name="avatar_image"),
    url(r"^__huey__", views.huey_test, name="huey_test"),
    url(r"^__dynamic__", views.dynamic_page, name="dynamic_page"),
    url(r"^__500__", views.preview_500, name="preview_500"),
    url(r"^(.*)", views.catchall, name="catchall"),
]
