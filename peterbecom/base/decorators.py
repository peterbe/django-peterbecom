import hashlib
import functools

from django.core.cache import cache
from django.utils.encoding import force_bytes


def lock_decorator(key_maker=None):
    """When you want to lock a view function from more than 1 call."""

    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            key = func.__qualname__
            if key_maker:
                key += key_maker(*args, **kwargs)
            else:
                key += str(args) + str(kwargs)
            lock_key = hashlib.md5(force_bytes(key)).hexdigest()
            with cache.lock(lock_key):
                return func(*args, **kwargs)

        return inner

    return decorator
