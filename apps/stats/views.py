from django.shortcuts import render
from apps.redisutils import get_redis_connection


def stats_index(request):
    data = {}
    redis = get_redis_connection()
    urls = {}

    def get_totals(prefix):
        total_hits = total_misses = 0
        for uri, count in redis.zrange('%s:hits' % prefix,
                                       0, -1, withscores=True):
            count = int(count)
            total_hits += count
            if uri not in urls:
                urls[uri] = {'hits': 0, 'misses': 0}
            urls[uri]['hits'] += count
        for uri, count in redis.zrange('%s:misses' % prefix,
                                       0, -1, withscores=True):
            count = int(count)
            total_misses += count
            if uri not in urls:
                urls[uri] = {'hits': 0, 'misses': 0}
            urls[uri]['misses'] += count
        if total_hits:
            total_ratio = round(100.0 * total_misses / total_hits, 1)
        else:
            total_ratio = ''
        return {'urls': urls,
                'total_hits': total_hits,
                'total_misses': total_misses,
                'total_ratio': total_ratio}

    data['plog'] = get_totals('plog')
    data['homepage'] = get_totals('homepage')

    for v in data['plog']['urls'].values():
        if v['hits']:
            v['ratio'] = '%.1f%%' % (100.0 * v['misses'] / v['hits'])
        else:
            v['ratio'] = '--'

    data['start_date'] = redis.get('counters-start')

    return render(request, 'stats/index.html', data)
