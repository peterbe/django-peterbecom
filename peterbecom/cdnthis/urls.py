from django.conf.urls import url

from . import views


app_name = 'cdnthis'

urlpatterns = [
    url('^$', views.index, name='index'),
    url('^nocaching/$', views.nocaching, name='nocaching'),
    url('^cached/$', views.cached, name='cached'),
]
