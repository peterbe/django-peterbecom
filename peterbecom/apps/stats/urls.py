from django.conf.urls.defaults import patterns, include, url

from . import views
urlpatterns = patterns('',
    url('^$', views.stats_index, name='stats_index'),
)
