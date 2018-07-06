import datetime

from django.conf import settings


THIS_YEAR = datetime.datetime.utcnow().year


def context(request):
    use_google_analytics = (
        not settings.DEBUG and "/plog/screenshot/" not in request.path
    )
    return {
        "use_google_analytics": use_google_analytics,
        "pingdom_rum_id": settings.PINGDOM_RUM_ID,
        "THIS_YEAR": THIS_YEAR,
        "ENABLE_CLIENT_SIDE_ROLLBAR": settings.ENABLE_CLIENT_SIDE_ROLLBAR,
    }
