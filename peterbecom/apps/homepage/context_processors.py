import datetime

from django.conf import settings


def context(request):
    return {
        'use_google_analytics': not settings.DEBUG,
        'THIS_YEAR': datetime.datetime.utcnow().year,
    }
