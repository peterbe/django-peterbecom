from django.http import HttpResponsePermanentRedirect
from django.conf.urls.defaults import patterns, include, url
from django.views.decorators.cache import cache_page
from .feed import PlogFeed
import views


urlpatterns = patterns('',
    url('^$', views.home, name='home'),
    url(r'(.*?)/?rss.xml$', cache_page(PlogFeed(), 60 * 60)),
    url('^search$', views.search, name='search'),
    url('^autocomplete$', views.autocomplete, name='autocomplete'),
    url('^autocomplete/tester$', views.autocomplete_tester, name='autocomplete_tester'),
    url('^About$', lambda x: HttpResponsePermanentRedirect('/about/')),
    url('^about$', views.about, name='about'),
    url('^contact$', views.contact, name='contact'),
    url('^oc-(.*)', views.home, name='only_category'),
    url('^zitemap.xml$', views.sitemap, name='sitemap'),
    url('^humans.txt$', views.humans_txt, name='humans_txt'),
    url('^(.*)', views.blog_post_by_alias, name='blog_post_by_alias'),
)
