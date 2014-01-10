import os
import time
import subprocess
from urlparse import urlparse

from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.conf import settings

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
