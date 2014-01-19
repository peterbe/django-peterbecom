import re
import os
import time
import subprocess
from urlparse import urlparse

from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.conf import settings
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt

from peterbecom.apps.plog.views import json_view

from . import models


COUNT_JS_PATH = os.path.join(
    os.path.dirname(__file__),
    'count.js'
)

def index(request):
    context = {}
    context['page_title'] = "Number of Domains"
    return render(request, 'nodomains/index.html', context)


def run_queued(queued):
    url = queued.url
    result = run_url(url)
    queued.delete()
    return result


def run_url(url):
    t0 = time.time()
    command = [
        settings.PHANTOMJS_PATH,
        '--ignore-ssl-errors=true',
        COUNT_JS_PATH,
        '"%s"' % url
    ]
    print "Running"
    print command
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

    return {'domains': domains, 'count': len(domains)}


@csrf_exempt
@require_POST
@json_view
def run(request):
    url = request.POST['url']
    if url.isdigit():
        raise NotImplementedError(url)
    try:
        parsed = urlparse(url)
        assert parsed.scheme in ('https', 'http'), 'not a httpish thing'
        assert parsed.netloc, 'no path'
        assert '"' not in url, 'quotes :('
    except AssertionError as msg:
        return {'error': str(msg)}

    url = re.sub('((utm_campaign|utm_source|utm_medium)=(.*)&?)', '', url)
    if url.endswith('?'):
        url = url[:-1]

    try:
        result = models.Result.objects.get(url=url)
        domains = [
            x['domain'] for x in
            models.ResultDomain.objects.filter(result=result).values('domain')
        ]
        return {'count': result.count, 'domains': domains}
    except models.Result.DoesNotExist:
        pass
    queued, __ = models.Queued.objects.get_or_create(url=url)
    if 0 and models.Queued.objects.all().count() <= 1:
        print "Run Queued"
        return run_queued(queued)
    else:
        behind = models.Queued.objects.filter(add_date__lt=queued.add_date).count()
        return {'queued': queued.pk, 'behind': behind}


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
