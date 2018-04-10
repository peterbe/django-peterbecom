from django.conf.urls import url, include

from rest_framework import routers
from . import views


router = routers.DefaultRouter()
router.register(
    r'blogitems',
    views.BlogitemViewSet,
    base_name='blogitem'
)
router.register(
    r'categories',
    views.CategoryViewSet,
    base_name='category'
)

app_name = 'api'

urlpatterns = [
    url(r'^v1/', include(router.urls)),
]
