from contextlib import contextmanager

from django.core.cache.backends.locmem import LocMemCache


class LockMemCache(LocMemCache):
    """Really dumb extension of LocMemCache that has a `lock` context manager."""

    @contextmanager
    def lock(self, key):
        yield
