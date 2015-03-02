from django.conf.urls.defaults import patterns, include, url


from . import views
urlpatterns = patterns('',
    url('^$', views.index, name='index'),
    url('^store$', views.store, name='store'),
    url('^localforage.html$', views.localforage, name='localforage'),
    url('^localstorage.html$', views.localstorage, name='localstorage'),
)
