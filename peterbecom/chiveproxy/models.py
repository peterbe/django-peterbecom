from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


class Card(models.Model):
    url = models.URLField(max_length=400, db_index=True)
    text = models.CharField(max_length=200, default="")
    data = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def get_text(self, default=""):
        return self.data.get("text") or default

    def __str__(self):
        return self.url


@receiver(pre_save, sender=Card)
def set_text(sender, instance, **kwargs):
    if not instance.text and instance.data:
        instance.text = instance.data.get("text") or ""


@receiver(post_save, sender=Card)
def preload_image_proxies(sender, instance, **kwargs):
    print(f"Preloading image proxies for {instance}")

    # deliberately lazy import to avoid circular import issues
    from peterbecom.chiveproxy.tasks import preload_image_proxies_task

    preload_image_proxies_task(instance.id, sleep_delay=1)
