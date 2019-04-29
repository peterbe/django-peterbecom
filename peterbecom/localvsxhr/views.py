import re
from collections import defaultdict

from django.shortcuts import render
from django import http
from django.views.decorators.http import require_POST

from peterbecom.plog.views import json_view
from peterbecom.localvsxhr.models import Measurement, BootMeasurement
from peterbecom.localvsxhr import forms


def index(request):
    context = {
        "page_title": "Local vs. XHR",
        "count_measurements": Measurement.objects.all().count(),
        "count_boot_measurements": BootMeasurement.objects.all().count(),
    }
    return render(request, "localvsxhr/index.html", context)


simple_user_agent_regex = re.compile(
    r"""
    Firefox/\d+ |
    Chrome/\d+ |
    Safari/\d+
""",
    re.X,
)


def parse_user_agent(ua):
    browser = ""
    version = None
    if "iPhone OS" in ua:
        browser = "iPhone "
    elif "AppleWebKit" in ua and "Chrome" in ua:
        browser = "AppleWebKit "
    elif "Mobile;" in ua:
        browser = "Mobile "
    elif "SeaMonkey/" in ua:
        browser = "SeaMonkey "
    elif "Trident/" in ua:
        browser = "Internet Explorer"
        version = re.findall(r"rv:(\d+)", ua)[0]

    for match in simple_user_agent_regex.findall(ua):
        browser += match.split("/")[0]
        version = match.split("/")[1]
        break
    return browser, version


def stats(request):
    context = {}
    # for m in Measurement.objects.all():
    #     m.save()

    def _stats(r):
        # returns the median, average and standard deviation of a sequence
        tot = sum(r)
        avg = tot / len(r)
        sdsq = sum([(i - avg) ** 2 for i in r])
        s = list(r)
        s.sort()
        return s[len(s) // 2], avg, (sdsq / (len(r) - 1 or 1)) ** 0.5

    def wrap_sequence(data):
        items = []
        for key in sorted(data, key=lambda x: x and x.lower() or ""):
            median, average, stddev = _stats(data[key])
            items.append(
                {
                    "name": key or "plain localStorage",
                    "median": median,
                    "average": average,
                    "stddev": stddev,
                    "count": len(data[key]),
                    "max": max(data[key]),
                    "min": min(data[key]),
                }
            )
        return items

    def wrap_sequence_boots(data):
        items = []
        for key in sorted(data, key=lambda x: x.lower()):
            times1 = [x[0] for x in data[key]]
            times2 = [x[1] for x in data[key]]
            median1, average1, stddev1 = _stats(times1)
            median2, average2, stddev2 = _stats(times2)
            items.append(
                {
                    "name": key or "plain localStorage",
                    "median1": median1,
                    "average1": average1,
                    "stddev1": stddev1,
                    "median2": median2,
                    "average2": average2,
                    "stddev2": stddev2,
                    "max1": max(times1),
                    "min1": min(times1),
                    "max2": max(times2),
                    "min2": min(times2),
                    "count": len(data[key]),
                }
            )
        return items

    drivers = defaultdict(list)
    browsers = defaultdict(list)
    # browserversions = defaultdict(list)
    for m in Measurement.objects.all():
        drivers[m.driver].append(m.local_median)
        drivers["XHR"].append(m.xhr_median)
        browser, version = parse_user_agent(m.user_agent)
        if browser:
            browsers[browser].append(m.local_median)
            # if version:
            #     browserversions['%s %s' % (browser, version)].append(
            #         m.xhr_median
            #     )
    context["drivers"] = wrap_sequence(drivers)
    context["browsers"] = wrap_sequence(browsers)
    # context['browserversions'] = wrap_sequence(browserversions)

    boots = defaultdict(list)
    for m in BootMeasurement.objects.all():
        boots[m.driver].append((m.time_to_boot1, m.time_to_boot2))
    context["boots"] = wrap_sequence_boots(boots)

    return render(request, "localvsxhr/stats.html", context)


def localforage(request):
    context = {"page_title": "localForage vs. XHR"}
    return render(request, "localvsxhr/localforage.html", context)


def localforage_localstorage(request):
    context = {"page_title": "localForage (localStorage driver) vs. XHR"}
    return render(request, "localvsxhr/localforage_localstorage.html", context)


def localstorage(request):
    context = {"page_title": "localStorage vs. XHR"}
    return render(request, "localvsxhr/localstorage.html", context)


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


@json_view
def download_json(request):
    context = {"measurements": [], "boot_measurements": []}
    for m in Measurement.objects.all():
        context["measurements"].append(
            {
                "url": m.url,
                "user_agent": m.user_agent,
                "driver": m.driver,
                "xhr_median": m.xhr_median,
                "local_median": m.local_median,
                "plain_localstorage": m.plain_localstorage,
                "iterations": m.iterations,
                "add_date": m.add_date,
            }
        )

    for m in BootMeasurement.objects.all():
        context["boot_measurements"].append(
            {
                "time_to_boot1": m.time_to_boot1,
                "time_to_boot2": m.time_to_boot2,
                "plain_localstorage": m.plain_localstorage,
                "driver": m.driver,
                "add_date": m.add_date,
                "user_agent": m.user_agent,
            }
        )

    return context
