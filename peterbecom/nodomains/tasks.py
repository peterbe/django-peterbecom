import re
import os
import time

import subprocess32

from django.conf import settings

from celery.task import task

from . import models


COUNT_JS_PATH = os.path.join(
    os.path.dirname(__file__),
    'count.js'
)


@task()
def run_queued(queued):
    url = queued.url
    result = run_url(url)
    if result.get('error'):
        queued.failed_attempts += 1
        queued.save()
    else:
        queued.delete()
    return result


def run_url(url, dry_run=False):
    t0 = time.time()
    command = [
        settings.PHANTOMJS_PATH,
        '--ignore-ssl-errors=true',
        COUNT_JS_PATH,
        '"%s"' % url
    ]
    print "Running"
    print command
    process = subprocess32.Popen(
        ' '.join(command),
        shell=True,
        stdout=subprocess32.PIPE,
        stderr=subprocess32.PIPE
    )
    out, err = process.communicate(timeout=60)
    t1 = time.time()

    print "TOOK", t1 - t0

    regex = re.compile('DOMAIN: (.*) COUNT: (\d+)')
    domains = {}
    for line in out.splitlines():
        if line.startswith('DOMAIN: '):
            try:
                domain, count = regex.findall(line)[0]
                count = int(count)
                domains[domain] = count
            except IndexError:
                print "Rogue line", repr(line)

    print "OUT", '-' * 70
    print out
    # print repr(out)
    print "ERR", '-' * 70
    print err
    # print repr(err)
    print "\n"
    if domains:
        if not dry_run:
            r = models.Result.objects.create(
                url=url,
                count=len(domains)
            )
            for domain in domains:
                models.ResultDomain.objects.create(
                    result=r,
                    domain=domain,
                    count=domains[domain]
                )
    else:
        return {'error': "Unable to download that URL. It's not you, it's me!"}

    return {'domains': domains, 'count': len(domains)}
