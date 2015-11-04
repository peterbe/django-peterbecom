import datetime

from django.conf import settings


def context(request):
    return {
        'use_google_analytics': not settings.DEBUG,
        'pingdom_rum_id': settings.PINGDOM_RUM_ID,
        'THIS_YEAR': datetime.datetime.utcnow().year,
    }
