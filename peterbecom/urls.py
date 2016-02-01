from django import http
from django.conf.urls import patterns, include, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

import djcelery

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^nodomains$', lambda x: http.HttpResponseRedirect('/nodomains/')),
    url(r'^nodomains/', include('peterbecom.apps.nodomains.urls', namespace='nodomains')),
    url(r'^ajaxornot/', include('peterbecom.apps.ajaxornot.urls', namespace='ajaxornot')),
    url(r'^cdnthis$', lambda x: http.HttpResponseRedirect('/cdnthis/')),
    url(r'^cdnthis/', include('peterbecom.apps.cdnthis.urls', namespace='cdnthis')),
    url(r'^localvsxhr$', lambda x: http.HttpResponseRedirect('/localvsxhr/')),
    url(r'^localvsxhr/', include('peterbecom.apps.localvsxhr.urls', namespace='localvsxhr')),
    url(r'^stats/', include('peterbecom.apps.stats.urls')),
    url(r'^plog/', include('peterbecom.apps.plog.urls')),
    url(r'^plog$', lambda x: http.HttpResponseRedirect('/plog/')),
    url(r'', include('peterbecom.apps.homepage.urls')),
    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
)

urlpatterns += staticfiles_urlpatterns()


djcelery.setup_loader()
