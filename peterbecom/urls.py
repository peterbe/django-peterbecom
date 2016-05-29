from django import http
from django.conf.urls import patterns, include, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import djcelery

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns(
    '',
    url(
        r'^admin/',
        include(admin.site.urls)
    ),
    url(
        r'^nodomains$',
        lambda x: http.HttpResponseRedirect('/nodomains/')
    ),
    url(
        r'^nodomains/',
        include('peterbecom.nodomains.urls', namespace='nodomains')
    ),
    url(
        r'^ajaxornot/',
        include('peterbecom.ajaxornot.urls', namespace='ajaxornot')
    ),
    url(
        r'^cdnthis$',
        lambda x: http.HttpResponseRedirect('/cdnthis/')
    ),
    url(
        r'^cdnthis/',
        include('peterbecom.cdnthis.urls', namespace='cdnthis')
    ),
    url(
        r'^localvsxhr$',
        lambda x: http.HttpResponseRedirect('/localvsxhr/')
    ),
    url(
        r'^localvsxhr/',
        include('peterbecom.localvsxhr.urls', namespace='localvsxhr')
    ),
    url(
        r'^podcasttime$',
        lambda x: http.HttpResponseRedirect('/podcasttime/')
    ),
    url(
        r'^podcasttime/',
        include('peterbecom.podcasttime.urls', namespace='podcasttime')
    ),
    url(
        r'^stats/',
        include('peterbecom.stats.urls')
    ),
    url(
        r'^plog/',
        include('peterbecom.plog.urls')
    ),
    url(
        r'^plog$',
        lambda x: http.HttpResponseRedirect('/plog/')
    ),
    url(
        r'',
        include('peterbecom.homepage.urls')
    ),
)

urlpatterns += staticfiles_urlpatterns()


djcelery.setup_loader()
