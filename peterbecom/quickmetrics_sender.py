import requests
from django.conf import settings


def quickmetrics_event(name, value=1, dimension=None, swallow_exceptions=False):
    if not settings.QUICKMETRICS_API_KEY:
        return
    payload = {"name": name, "value": value, "dimension": dimension}

    url = "https://qckm.io/json"
    try:
        r = requests.post(
            url, json=payload, headers={"x-qm-key": settings.QUICKMETRICS_API_KEY}
        )
        r.raise_for_status()
        print("QUICKMETRICS", r.status_code, str(payload))
    except Exception as exception:
        if swallow_exceptions:
            print("QUICKMETRICS EXCEPTION", exception)
        else:
            raise
