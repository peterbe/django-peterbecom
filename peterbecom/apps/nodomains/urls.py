from django.conf.urls.defaults import patterns, include, url


from . import views
urlpatterns = patterns('',
    url('^$', views.index, name='nodomains_index'),
    url('^run$', views.run, name='nodomains_run'),
)
