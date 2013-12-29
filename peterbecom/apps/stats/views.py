from django.shortcuts import render
from peterbecom.apps.redisutils import get_redis_connection


def stats_index(request):
    data = {}
    redis = get_redis_connection()
    urls = {}

    def get_totals(prefix):
        total_hits = total_misses = 0
        for uri, count in redis.zrevrange('%s:hits' % prefix,
                                       0, 100, withscores=True):
            count = int(count)
            total_hits += count
            if uri not in urls:
                urls[uri] = {'hits': 0, 'misses': 0}
            urls[uri]['hits'] += count
        for uri, count in redis.zrevrange('%s:misses' % prefix,
                                       0, 100, withscores=True):
            count = int(count)
            total_misses += count
            if uri not in urls:
                urls[uri] = {'hits': 0, 'misses': 0}
            urls[uri]['misses'] += count
        if total_hits:
            total_ratio = round(100.0 * total_misses / total_hits, 1)
        else:
            total_ratio = ''
        return {#'urls': urls,
                'total_hits': total_hits,
                'total_misses': total_misses,
                'total_ratio': total_ratio}

    data['plog'] = get_totals('plog')
    data['homepage'] = get_totals('homepage')

    total_hits = total_misses = 0
    for v in urls.values():
        total_hits += v['hits']
        total_misses += v['misses']
        if v['hits']:
            v['ratio'] = '%.1f%%' % (100.0 * v['misses'] / v['hits'])
        else:
            v['ratio'] = '--'
    def make_abs_url(url):
        if url.startswith('GET '):
            return url[4:]
        return None
    urls = [(make_abs_url(x), x, y['hits'], y['misses'], y['ratio'])
            for x, y in urls.items()]
    urls.sort(lambda x, y: cmp(y[1], x[1]))
    data['urls'] = urls

    data['start_date'] = redis.get('counters-start')
    data['total_hits'] = total_hits
    data['total_misses'] = total_misses

    return render(request, 'stats/index.html', data)
