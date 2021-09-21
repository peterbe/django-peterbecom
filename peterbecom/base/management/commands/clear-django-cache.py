from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    def handle(self, **options):
        count = 0
        for key in cache.iter_keys("*"):
            count += 1
        self.stdout.write(f"Cleared {count:,} cache keys")
        cache.clear()
