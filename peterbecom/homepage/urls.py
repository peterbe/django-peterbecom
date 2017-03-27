from django.http import HttpResponsePermanentRedirect
from django.conf.urls import url
from django.views.decorators.cache import cache_page
from .feed import PlogFeed
from . import views


urlpatterns = [
    url('^$', views.home, name='home'),
    url('^p(?P<page>\d+)$', views.home, name='home_paged'),
    url(r'(.*?)/?rss.xml$', cache_page(60 * 60 * 6)(PlogFeed())),
    url('^search$', views.search, name='search'),
    url('^autocompete/v1$', views.autocompete, name='autocompete'),
    url('^About$', lambda x: HttpResponsePermanentRedirect('/about/')),
    url('^about$', views.about, name='about'),
    url('^contact$', views.contact, name='contact'),
    url('^celerytester/$', views.celerytester, name='celerytester'),
    url('^signin/$', views.signin, name='signin'),
    url('^signout/$', views.signout, name='signout'),
    url('^oc-(?P<oc>.*)/p(?P<page>\d+)$', views.home,
        name='only_category_paged'),
    url('^oc-(?P<oc>.*)', views.home, name='only_category'),
    url('^zitemap.xml$', views.sitemap, name='sitemap'),
    url('^humans.txt$', views.humans_txt, name='humans_txt'),
    url('^(.*)', views.blog_post_by_alias, name='blog_post_by_alias'),
]
