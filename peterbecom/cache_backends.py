from contextlib import contextmanager

from django.core.cache.backends.locmem import LocMemCache


# IS THIS EVEN USED ANYWHERE??


class LockMemCache(LocMemCache):
    """Really dumb extension of LocMemCache that has a `lock` context manager."""

    @contextmanager
    def lock(self, key):
        yield
