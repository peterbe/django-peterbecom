from django.conf.urls.defaults import patterns, include, url
#from feeds import BustFeed

import views
urlpatterns = patterns('',
    url('^$', views.plog_index, name='plog_index'),
    url('^edit/(.*)', views.edit_post, name='edit_post'),
    url('^thumbnails/delete/', views.delete_post_thumbnail, name='delete_post_thumbnail'),
    url('^thumbnails/(.*)', views.post_thumbnails, name='post_thumbnails'),
    url('^calendar/$', views.calendar, name='calendar'),
    url('^calendar/data/$', views.calendar_data, name='calendar_data'),
    url('^add/$', views.add_post, name='add_post'),
    url('^add/file/$', views.add_file, name='plog_add_file'),
    url('^preview$', views.preview_post, name='plog_preview_post'),
    url('^new-comments$', views.new_comments, name='new_comments'),
    url('^prepare.json$', views.prepare_json, name='prepare'),
    url('^preview.json$', views.preview_json, name='preview'),
    url('^(.*)/submit$', views.submit_json, name='submit'),
    url('^(.*)/approve/(.*)', views.approve_comment, name='approve_comment'),
    url('^(.*)/delete/(.*)', views.delete_comment, name='delete_comment'),
    url('^(.*)', views.blog_post, name='blog_post'),
)
