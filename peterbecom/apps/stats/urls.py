from django.conf.urls import patterns, include, url

from . import views
urlpatterns = patterns('',
    url('^$', views.stats_index, name='stats_index'),
)
