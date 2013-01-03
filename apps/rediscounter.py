from django.utils.encoding import iri_to_uri
from apps.redisutils import get_redis_connection


def redis_increment(prefix, request):
    redis = get_redis_connection()
    full_path = request.get_full_path()
    if full_path != '/' and full_path.endswith('/'):
        full_path = full_path[:-1]
    value = '%s %s' % (request.method, iri_to_uri(full_path))
    redis.zincrby(prefix, value, 1)
