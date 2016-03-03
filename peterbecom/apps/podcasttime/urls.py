from django.conf.urls import patterns, url

from . import views


urlpatterns = patterns(
    '',
    url('^$', views.index, name='index'),
    url('^podcasts/$', views.podcasts, name='podcasts'),
    url('^picks/$', views.picks, name='picks'),
    url('^find$', views.find, name='find'),
    url('^calendar$', views.calendar, name='calendar'),
    url('^stats$', views.stats, name='stats'),
    url('^picked$', views.picked, name='picked'),
    url('^podcasts/(?P<id>\d+)/$', views.podcast, name='podcast'),
    url(
        '^podcasts/(?P<id>\d+)/(?P<slug>[-\w]+)$',
        views.podcast,
        name='podcast_slug'
    ),
)
