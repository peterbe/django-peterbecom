from django.conf.urls.defaults import patterns, include, url


from . import views
urlpatterns = patterns('',
    url('^$', views.index, name='index'),
    url('^domains$', views.domains, name='domains'),
    url('^run$', views.run, name='run'),
    url('^recently$', views.recently, name='recently'),
    url('^most-common$', views.most_common, name='most_common'),
    url('^hall-of-fame$', views.hall_of_fame, name='hall_of_fame'),
    url('^histogram$', views.histogram, name='histogram'),
)
