from django import http
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render

from .models import AWSProduct


@login_required
def all_keywords(request):

    if request.method == 'POST':
        asin = request.POST['asin']
        keyword = request.POST['keyword']
        awsproduct = AWSProduct.objects.get(asin=asin, keyword=keyword)
        awsproduct.disabled = not awsproduct.disabled
        awsproduct.save()
        return http.JsonResponse({'ok': True})

    awsproducts = AWSProduct.objects.all().order_by('disabled', 'modify_date')
    keywords = {}
    keywords_count = {}
    keywords_disabled = {}
    for awsproduct in awsproducts:
        if awsproduct.keyword not in keywords:
            keywords[awsproduct.keyword] = []
            keywords_count[awsproduct.keyword] = 0
            keywords_disabled[awsproduct.keyword] = 0
        keywords[awsproduct.keyword].append(awsproduct)
        keywords_count[awsproduct.keyword] += 1
        if awsproduct.disabled:
            keywords_disabled[awsproduct.keyword] += 1
    context = {
        'keywords': keywords,
        'keywords_count': keywords_count,
        'keywords_disabled': keywords_disabled,
        'keywords_sorted': sorted(keywords),
        'page_title': 'All Keywords',
    }
    return render(request, 'awspa/keywords.html', context)


@login_required
@require_POST
def delete_awsproduct(request):
    assert request.method == 'POST'
    asin = request.POST['asin']
    keyword = request.POST['keyword']
    awsproduct = AWSProduct.objects.get(asin=asin, keyword=keyword)
    awsproduct.delete()
    return http.JsonResponse({'ok': True})
