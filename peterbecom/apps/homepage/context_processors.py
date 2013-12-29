from django.conf import settings


def context(request):
    return {'use_google_analytics': not settings.DEBUG}
