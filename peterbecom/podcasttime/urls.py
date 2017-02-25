from django.conf.urls import url

from . import views


urlpatterns = [
    url('^$', views.index, name='index'),
    url('^podcasts/$', views.legacy_podcasts, name='podcasts'),
    url('^podcasts/data/$', views.podcasts_data, name='podcasts_data'),
    url('^podcasts/table/$', views.podcasts_table, name='podcasts_table'),

    url('^picks/$', views.legacy_picks, name='picks'),
    url('^picks/data/$', views.picks_data, name='picks_data'),
    url('^find$', views.find, name='find'),
    url('^stats$', views.stats, name='stats'),
    url('^stats/episodes$', views.stats_episodes, name='stats_episodes'),
    url('^picked$', views.picked, name='picked'),
    url(
        '^podcasts/episodes/(?P<id>\d+)$',
        views.podcast_episodes,
        name='podcast_episodes'
    ),
    url(
        '^general-stats/(numbers)$',
        views.general_stats,
        name='general_stats'
    ),
]
