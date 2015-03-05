from django.shortcuts import render
from django import http
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from peterbecom.apps.plog.views import json_view
from peterbecom.apps.localvsxhr.models import Measurement
from peterbecom.apps.localvsxhr import forms


def index(request):
    context = {
        'page_title': 'Local vs. XHR',
        'count_measurements': Measurement.objects.all().count(),
    }
    return render(request, 'localvsxhr/index.html', context)


def localforage(request):
    context = {
        'page_title': 'localForage vs. XHR',
    }
    return render(request, 'localvsxhr/localforage.html', context)


def localforage_localstorage(request):
    context = {
        'page_title': 'localForage (localStorage driver) vs. XHR',
    }
    return render(request, 'localvsxhr/localforage_localstorage.html', context)


def localstorage(request):
    context = {
        'page_title': 'localStorage vs. XHR',
    }
    return render(request, 'localvsxhr/localstorage.html', context)


@require_POST
@json_view
def store(request):
    form = forms.MeasurementForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    form.save()

    return True


@require_POST
@json_view
def store_boot(request):
    form = forms.BootMeasurementForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    form.save()

    return True
