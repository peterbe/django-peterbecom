from django.http import HttpResponsePermanentRedirect
from django.conf.urls.defaults import patterns, include, url
from .feed import PlogFeed
import views


urlpatterns = patterns('',
    url('^$', views.home, name='home'),
    (r'^rss.xml$', PlogFeed()),
    url('^search$', views.search, name='search'),
    url('^About$', lambda x: HttpResponsePermanentRedirect('/about/')),
    url('^about$', views.about, name='about'),
    url('^contact$', views.contact, name='contact'),
    url('^oc-(.*)', views.home, name='only_category'),
    url('^zitemap.xml$', views.sitemap, name='sitemap'),
)
