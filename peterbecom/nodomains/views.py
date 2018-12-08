from django.shortcuts import render
from django.views.decorators.cache import cache_page

from peterbecom.plog.views import json_view

from . import models


ONE_MONTH = 60 * 60 * 24 * 30


@cache_page(ONE_MONTH)
def index(request):
    context = {}
    context["page_title"] = "Number of Domains"
    return render(request, "nodomains/index.html", context)


@cache_page(ONE_MONTH)
@json_view
def histogram(request):
    rows = [["URL", "Count"]]
    for x in models.Result.objects.all().values("url", "count"):
        rows.append([x["url"], x["count"]])
    return rows
