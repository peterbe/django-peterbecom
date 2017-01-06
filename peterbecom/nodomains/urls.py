from django.conf.urls import url


from . import views
urlpatterns = [
    url('^$', views.index, name='index'),
    url('^domains$', views.domains, name='domains'),
    url('^numbers$', views.numbers, name='numbers'),
    url('^run$', views.run, name='run'),
    url('^recently$', views.recently, name='recently'),
    url('^most-common$', views.most_common, name='most_common'),
    url('^hall-of-fame$', views.hall_of_fame, name='hall_of_fame'),
    url('^histogram$', views.histogram, name='histogram'),
]
