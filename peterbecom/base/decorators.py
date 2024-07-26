import functools
import hashlib

from django.core.cache import cache
from django.utils.cache import patch_cache_control
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


def variable_cache_control(**kwargs):
    """Same as django.views.decorators.cache.cache_control except this one will
    allow the `max_age` parameter be a callable.
    """

    def _cache_controller(viewfunc):
        @functools.wraps(viewfunc)
        def _cache_controlled(request, *args, **kw):
            response = viewfunc(request, *args, **kw)
            copied = kwargs
            if kwargs.get("max_age") and callable(kwargs["max_age"]):
                max_age = kwargs["max_age"](request, *args, **kw)
                # Can't re-use, have to create a shallow clone.
                copied = dict(kwargs, max_age=max_age)
            patch_cache_control(response, **copied)
            return response

        return _cache_controlled

    return _cache_controller
