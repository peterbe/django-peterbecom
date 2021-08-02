from django.urls import re_path

from . import views


app_name = "ajaxornot"

urlpatterns = [
    re_path("^$", views.index, name="index"),
    re_path("^view1$", views.view1, name="view1"),
    re_path("^view2$", views.view2, name="view2"),
    re_path("^view2-table$", views.view2_table, name="view2_table"),
    re_path("^view3$", views.view3, name="view3"),
    re_path("^view3-data$", views.view3_data, name="view3_data"),
    re_path("^view4$", views.view4, name="view4"),
    re_path("^view5$", views.view5, name="view5"),
    re_path("^view5-table$", views.view5_table, name="view5_table"),
    re_path("^view6$", views.view6, name="view6"),
    re_path("^view6-data$", views.view6_data, name="view6_data"),
    re_path("^view7a$", views.view7a, name="view7a"),
    re_path("^view7b$", views.view7b, name="view7b"),
]
