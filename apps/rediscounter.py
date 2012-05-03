from django.utils.encoding import iri_to_uri
from apps.redisutils import get_redis_connection


def redis_increment(prefix, request):
    redis = get_redis_connection()
    value = '%s %s' % (request.method, iri_to_uri(request.get_full_path()))
    redis.zincrby(prefix, value, 1)
