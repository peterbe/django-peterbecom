from django.shortcuts import render
from django import http
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from peterbecom.apps.plog.views import json_view
from peterbecom.apps.localvsxhr.models import Measurement
from peterbecom.apps.localvsxhr.forms import MeasurementForm

# from fancy_cache import cache_page


# @cache_page(60 * 60)
def index(request):
    context = {
        'page_title': 'Local vs. XHR',
        'count_measurements': Measurement.objects.all().count(),
    }
    return render(request, 'localvsxhr/index.html', context)


def localforage(request):
    context = {
        'page_title': 'LocalForage vs. XHR',
    }
    return render(request, 'localvsxhr/localforage.html', context)


def localstorage(request):
    context = {
        'page_title': 'localStorage vs. XHR',
    }
    return render(request, 'localvsxhr/localstorage.html', context)


@csrf_exempt
@require_POST
@json_view
def store(request):
    form = MeasurementForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    form.save()

    return True
