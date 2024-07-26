from django.core.cache import cache
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from peterbecom.plog.models import BlogComment, BlogItem, Category


def _reset_cache_page_decorations():
    for key in cache.keys(
        search="views.decorators.cache.cache_page.publicapi_cache_page.*"
    ):
        print("Deleting cache_page cache key", key)
        cache.delete(key)


@receiver(post_save, sender=BlogItem)
@receiver(pre_delete, sender=BlogItem)
@receiver(post_save, sender=BlogComment)
@receiver(pre_delete, sender=BlogComment)
@receiver(post_save, sender=Category)
def invalidate_cache_page_decorations(sender, instance, **kwargs):
    _reset_cache_page_decorations()


# This is manually run from `publicapi.apps.PublicAPIConfig.ready`
# when things start up.
# Because the caching is done centrally, in Redis, we want to reset those
# in case the software has changed and not a specific model instance.
def run_all_now():
    _reset_cache_page_decorations()
