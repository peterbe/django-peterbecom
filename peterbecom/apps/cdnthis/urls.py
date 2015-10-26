from django.conf.urls import patterns, url


from . import views


urlpatterns = patterns(
    '',
    url('^$', views.index, name='index'),
    url('^/nocaching/$', views.nocaching, name='nocaching'),
    url('^/cached/$', views.cached, name='cached'),
)
