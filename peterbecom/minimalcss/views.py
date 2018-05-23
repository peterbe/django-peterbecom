import json
import time
from urllib.parse import urlparse

import requests

from django import http
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .models import Minimization


@csrf_exempt
def minimize(request):
    if request.method == 'OPTIONS':
        response = http.HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        CORS_ALLOW_HEADERS = (
            'accept',
            'accept-encoding',
            'authorization',
            'content-type',
            'dnt',
            'origin',
            'user-agent',
            'x-csrftoken',
            'x-requested-with',
        )
        response['Access-Control-Allow-Headers'] = ', '.join(
            CORS_ALLOW_HEADERS
        )
        CORS_ALLOW_METHODS = (
            'OPTIONS',
            'POST',
        )
        response['Access-Control-Allow-Methods'] = ', '.join(
            CORS_ALLOW_METHODS
        )
        return response
    elif request.method != 'POST':
        return http.HttpResponseNotAllowed(['POST'])
    options = json.loads(request.body.decode('utf-8'))
    url = options.get('url')
    if not url:
        return http.HttpResponseBadRequest('No url')
    parsed = urlparse(url)

    if not (parsed.scheme and parsed.netloc and parsed.path):
        return http.HttpResponseBadRequest(
            'url={!r} parsed={}'.format(
                url, parsed
            )
        )

    t0 = time.time()
    r = requests.post(
        settings.MINIMALCSS_SERVER_URL + '/minimize',
        json={'url': url},
    )
    if r.status_code != 200:
        print(
            "WARNING! "
            "{} status code trying to minimize {}".format(
                r.status_code,
                url
            )
        )
        return http.JsonResponse({
            'status_code': r.status_code,
        }, status_code=500)

    result = r.json()['result']
    t1 = time.time()

    Minimization.objects.create(
        url=url,
        time_took=t1 - t0,
        result=result,
    )

    response = http.JsonResponse({'result': result})
    response['Access-Control-Allow-Origin'] = '*'
    return response
