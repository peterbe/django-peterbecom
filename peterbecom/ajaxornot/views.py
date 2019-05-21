from collections import defaultdict

from django.shortcuts import render
from django.views.decorators.cache import cache_control

from peterbecom.plog.models import BlogItem, Category
from peterbecom.plog.utils import utc_now
from peterbecom.plog.views import json_view

ONE_MONTH = 60 * 60 * 24 * 30


@cache_control(public=True, max_age=ONE_MONTH)
def index(request):
    return render(request, "ajaxornot/index.html")


def get_data(max_length=1000, pub_date_format=None, offset=0):
    items = []
    category_names = dict((x.id, x.name) for x in Category.objects.all())
    categories = defaultdict(list)
    for e in BlogItem.categories.through.objects.all():
        categories[e.blogitem_id].append(category_names[e.category_id])
    qs = BlogItem.objects.filter(pub_date__lt=utc_now()).order_by("-pub_date")
    for item in qs[offset:max_length]:
        pub_date = item.pub_date
        if pub_date_format:
            pub_date = pub_date_format(pub_date)
        items.append(
            {
                "title": item.title,
                "slug": item.oid,
                "pub_date": pub_date,
                "keywords": [x for x in item.proper_keywords if x][:3],
                "categories": categories[item.id][:3],
            }
        )
    return items


@cache_control(public=True, max_age=ONE_MONTH)
def view1(request):
    context = {"items": get_data()}
    return render(request, "ajaxornot/view1.html", context)


@cache_control(public=True, max_age=ONE_MONTH)
def view2(request):
    return render(request, "ajaxornot/view2.html")


@cache_control(public=True, max_age=ONE_MONTH)
def view2_table(request):
    context = {"items": get_data()}
    return render(request, "ajaxornot/view2_table.html", context)


@cache_control(public=True, max_age=ONE_MONTH)
def view3(request):
    return render(request, "ajaxornot/view3.html")


@cache_control(public=True, max_age=ONE_MONTH)
@json_view
def view3_data(request):
    return {"items": get_data(pub_date_format=lambda x: x.strftime("%B %Y"))}


@cache_control(public=True, max_age=ONE_MONTH)
def view4(request):
    data = get_data(pub_date_format=lambda x: x.strftime("%B %Y"))
    context = {"items": data}
    return render(request, "ajaxornot/view4.html", context)


@cache_control(public=True, max_age=ONE_MONTH)
def view5(request):
    context = {"items": get_data(max_length=25)}
    return render(request, "ajaxornot/view5.html", context)


@cache_control(public=True, max_age=ONE_MONTH)
def view5_table(request):
    context = {"items": get_data(offset=25)}
    return render(request, "ajaxornot/view5_trs.html", context)


@cache_control(public=True, max_age=ONE_MONTH)
def view6(request):
    return render(request, "ajaxornot/view6.html")


@cache_control(public=True, max_age=ONE_MONTH)
@json_view
def view6_data(request):
    return {"items": get_data(pub_date_format=lambda x: x.strftime("%B %Y"))}


@cache_control(public=True, max_age=ONE_MONTH)
def view7a(request):
    return render(request, "ajaxornot/view7a.html")


@cache_control(public=True, max_age=ONE_MONTH)
def view7b(request):
    return render(request, "ajaxornot/view7b.html")
