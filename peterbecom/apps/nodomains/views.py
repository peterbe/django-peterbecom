import os
import time
import subprocess
from urlparse import urlparse

from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.conf import settings
from django.db.models import Count
from fancy_cache import cache_page

from peterbecom.apps.plog.views import json_view

from . import models


COUNT_JS_PATH = os.path.join(
    os.path.dirname(__file__),
    'count.js'
)

@cache_page(60 * 60)
def index(request):
    context = {}
    context['page_title'] = "Number of Domains"
    return render(request, 'nodomains/index.html', context)



@require_POST
@json_view
def run(request):
    url = request.POST['url']
    try:
        assert urlparse(url).scheme in ('https', 'http'), 'not a httpish thing'
        assert urlparse(url).netloc, 'no path'
        assert '"' not in url, 'quotes :('
    except AssertionError as msg:
        return {'error': str(msg)}

    t0 = time.time()
    command = [
        settings.PHANTOMJS_PATH,
        '--ignore-ssl-errors=true',
        COUNT_JS_PATH,
        '"%s"' % url
    ]
    process = subprocess.Popen(
        ' '.join(command),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = process.communicate()
    t1 = time.time()

    domains = []
    for line in out.splitlines():
        if line.startswith('DOMAIN: '):
            domains.append(line.replace('DOMAIN: ', '').strip())

    print "OUT", '-' * 70
    print out
    #print repr(out)
    print "ERR", '-' * 70
    print err
    #print repr(err)
    print "\n"
    if domains:
        r = models.Result.objects.create(
            url=url,
            count=len(domains)
        )
        for domain in domains:
            models.ResultDomain.objects.create(
                result=r,
                domain=domain
            )
    else:
        return {'error': "Unable to download that URL. It's not you, it's me!"}

    return {'domain': domains, 'count': len(domains)}


@json_view
def most_common(request):
    domains = []
    qs = (
        models.ResultDomain.objects
        .values('domain')
        .annotate(count=Count('domain'))
        .order_by('-count')
        .filter(count__gt=1)
    )
    for each in qs[:10]:
        domains.append([each['domain'], each['count']])

    return domains


@json_view
def recently(request):
    recent = []
    qs = models.Result.objects.all().order_by('-add_date')
    for result in qs.values('url', 'count')[:20]:
        recent.append([result['url'], result['count']])
    count = models.Result.objects.all().count()
    return {'recent': recent, 'count': count}


@json_view
def hall_of_fame(request):
    rows = []
    qs = models.Result.objects.all().values('url', 'count')
    for result in qs.order_by('-count')[:20]:
        rows.append([result['url'], result['count']])
    return rows


@json_view
def histogram(request):
    rows = [['URL', 'Count']]
    for x in models.Result.objects.all().values('url', 'count'):
        rows.append([x['url'], x['count']])
    return rows
