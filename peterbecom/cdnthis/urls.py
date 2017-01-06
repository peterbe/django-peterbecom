from django.conf.urls import url


from . import views


urlpatterns = [
    url('^$', views.index, name='index'),
    url('^nocaching/$', views.nocaching, name='nocaching'),
    url('^cached/$', views.cached, name='cached'),
]
