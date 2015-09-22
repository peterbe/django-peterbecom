from django.conf.urls import patterns, include, url


from . import views
urlpatterns = patterns('',
    url('^$', views.index, name='index'),
    url('^view1$', views.view1, name='view1'),
    url('^view2$', views.view2, name='view2'),
    url('^view2-table$', views.view2_table, name='view2_table'),
    url('^view3$', views.view3, name='view3'),
    url('^view3-data$', views.view3_data, name='view3_data'),
    url('^view4$', views.view4, name='view4'),
    url('^view5$', views.view5, name='view5'),
    url('^view5-table$', views.view5_table, name='view5_table'),
    url('^view6$', views.view6, name='view6'),
    url('^view6-data$', views.view6_data, name='view6_data'),
    url('^view7a$', views.view7a, name='view7a'),
    url('^view7b$', views.view7b, name='view7b'),

)
