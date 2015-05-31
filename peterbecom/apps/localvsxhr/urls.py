from django.conf.urls import patterns, include, url


from . import views
urlpatterns = patterns('',
    url('^$', views.index, name='index'),
    url('^stats$', views.stats, name='stats'),
    url('^download.json$', views.download_json, name='download_json'),
    url('^store$', views.store, name='store'),
    url('^store/boot$', views.store_boot, name='store_boot'),
    url('^localforage.html$', views.localforage, name='localforage'),
    url('^localforage-localstorage.html$',
        views.localforage_localstorage, name='localforage_localstorage'),
    url('^localstorage.html$', views.localstorage, name='localstorage'),
)
