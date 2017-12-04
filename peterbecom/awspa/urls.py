from django.conf.urls import url

from . import views


urlpatterns = [
    url('^keywords$', views.all_keywords, name='all_keywords'),
    url('^delete$', views.delete_awsproduct, name='delete_awsproduct'),
]
