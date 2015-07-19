from django.shortcuts import render, get_object_or_404, redirect

from peterbecom.apps.plog.views import json_view
from peterbecom.apps.plog.models import BlogItem
from peterbecom.apps.plog.utils import utc_now

from fancy_cache import cache_page


@cache_page(60 * 60)
def index(request):
    return render(request, 'ajaxornot/index.html')


def get_data(max_length=1000, pub_date_format=None, offset=0):
    items = []
    qs = BlogItem.objects.filter(pub_date__lt=utc_now()).order_by('-pub_date')
    for item in qs[offset:max_length]:
        pub_date = item.pub_date
        if pub_date_format:
            pub_date = pub_date_format(pub_date)
        items.append({
            'title': item.title,
            'slug': item.oid,
            'pub_date': pub_date,
            'keywords': [x for x in item.keywords if x][:3],
            'categories': [x.name for x in item.categories.all()[:3]]
        })
    return items


@cache_page(60 * 60)
def view1(request):
    context = {'items': get_data()}
    return render(request, 'ajaxornot/view1.html', context)


@cache_page(60 * 60)
def view2(request):
    return render(request, 'ajaxornot/view2.html')


@cache_page(60 * 60)
def view2_table(request):
    context = {'items': get_data()}
    return render(request, 'ajaxornot/view2_table.html', context)


@cache_page(60 * 60)
def view3(request):
    return render(request, 'ajaxornot/view3.html')


@cache_page(60 * 60)
@json_view
def view3_data(request):
    return {'items': get_data(pub_date_format=lambda x: x.strftime('%B %Y'))}


@cache_page(60 * 60)
def view4(request):
    data = get_data(pub_date_format=lambda x: x.strftime('%B %Y'))
    context = {'items': data}
    return render(request, 'ajaxornot/view4.html', context)


@cache_page(60 * 60)
def view5(request):
    context = {'items': get_data(max_length=25)}
    return render(request, 'ajaxornot/view5.html', context)


@cache_page(60 * 60)
def view5_table(request):
    context = {'items': get_data(offset=25)}
    return render(request, 'ajaxornot/view5_trs.html', context)


@cache_page(60 * 60)
def view6(request):
    return render(request, 'ajaxornot/view6.html')


@cache_page(60 * 60)
@json_view
def view6_data(request):
    return {'items': get_data(pub_date_format=lambda x: x.strftime('%B %Y'))}
