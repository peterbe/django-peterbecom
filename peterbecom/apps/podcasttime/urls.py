from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url('^$', views.index, name='index'),
    url('^podcasts/$', views.podcasts, name='podcasts'),
    url('^find$', views.find, name='find'),
    url('^calendar$', views.calendar, name='calendar'),
    url('^stats$', views.stats, name='stats'),
    url('^picked$', views.picked, name='picked'),
)
