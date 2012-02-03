from django.conf.urls.defaults import patterns, include, url
from .feed import PlogFeed

import views
urlpatterns = patterns('',
    url('^$', views.home, name='home'),
    (r'^rss.xml$', PlogFeed()),
    url('^search$', views.search, name='search'),
)
