from django.conf.urls import patterns, url

from . import views
urlpatterns = patterns(
    '',
    url('^$', views.stats_index, name='stats_index'),
)
