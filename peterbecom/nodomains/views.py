import re

from django import http
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt

from fancy_cache import cache_page

from peterbecom.plog.views import json_view

from . import models


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52


def index(request):
    context = {}
    context["page_title"] = "Number of Domains"
    return render(request, "nodomains/index.html", context)


@csrf_exempt
@require_POST
@json_view
def run(request):
    return http.HttpResponseBadRequest("Service discontinued.")


@json_view
def domains(request):
    url = request.GET.get("url", "")
    if not url:
        return http.HttpResponseBadRequest("No 'url'")

    domains_ = dict(
        (x["domain"], x["count"])
        for x in models.ResultDomain.objects.filter(result__url=url).values(
            "domain", "count"
        )
    )
    return {"domains": domains_}


def _stats(r):
    # returns the median, average and standard deviation of a sequence
    tot = sum(r)
    avg = tot / len(r)
    sdsq = sum([(i - avg) ** 2 for i in r])
    s = list(r)
    s.sort()
    return s[len(s) // 2], avg, (sdsq / (len(r) - 1 or 1)) ** .5


def _stats_prefixer(request):
    cache_key = "_stats_latest_add_date"
    value = cache.get(cache_key)
    if value is None:
        latest_result, = models.Result.objects.all().order_by("-add_date")[:1]
        value = str(latest_result.add_date)
        value = re.sub("[^\d]", "", value)
        cache.set(cache_key, value, ONE_DAY)

    return value


@cache_page(ONE_DAY, _stats_prefixer)
@json_view
def numbers(request):
    context = {}
    counts = models.Result.objects.all().values_list("count", flat=True)
    median, average, stddev = _stats(counts)
    context["average"] = "%.1f" % average
    context["median"] = "%.1f" % median
    context["stddev"] = "%.1f" % stddev
    context["total"] = len(counts)
    return context


@cache_page(ONE_DAY, _stats_prefixer)
@json_view
def most_common(request):
    domains = []
    qs = (
        models.ResultDomain.objects.values("domain")
        .annotate(count=Count("domain"))
        .order_by("-count")
        .filter(count__gt=1)
    )
    for each in qs[:10]:
        domains.append([each["domain"], each["count"]])

    return domains


@cache_page(ONE_DAY, _stats_prefixer)
@json_view
def recently(request):
    recent = []
    qs = models.Result.objects.all().order_by("-add_date")
    for result in qs.values("url", "count")[:20]:
        recent.append([result["url"], result["count"]])
    count = models.Result.objects.all().count()
    return {"recent": recent, "count": count}


@cache_page(ONE_DAY, _stats_prefixer)
@json_view
def hall_of_fame(request):
    rows = []
    qs = models.Result.objects.all().values("url", "count")
    for result in qs.order_by("-count")[:20]:
        rows.append([result["url"], result["count"]])
    return rows


@cache_page(ONE_DAY, _stats_prefixer)
@json_view
def histogram(request):
    rows = [["URL", "Count"]]
    for x in models.Result.objects.all().values("url", "count"):
        rows.append([x["url"], x["count"]])
    return rows
