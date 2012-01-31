from django.conf.urls.defaults import patterns, include, url
#from feeds import BustFeed

import views
urlpatterns = patterns('',
    url('^prepare.json$', views.prepare_json, name='prepare'),
    url('^preview.json$', views.preview_json, name='preview'),
    url('^(.*)/submit$', views.submit_json, name='submit'),
    url('^(.*)', views.blog_post, name='blog_post'),
    #url('^bilder/rss.xml', BustFeed()),
    #url('^bilder/(.*)', views.bust, name='bust'),
)
