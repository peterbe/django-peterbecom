from django.db import models
from django.db.models.signals import pre_save
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


class Picture(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="pictures")
    order_index = models.PositiveIntegerField(default=0)
    img = models.URLField(max_length=400)
    gifsrc = models.URLField(max_length=400, null=True, blank=True)
    mp4src = models.URLField(max_length=400, null=True, blank=True)
    caption = models.TextField(default="")
    caption_html = models.TextField(default="")
    transcription = models.TextField(default="")
    image_proxy_conversions = models.JSONField(default=dict)
    transcript = models.TextField(null=True, blank=True)
    transcript_error = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


@receiver(pre_save, sender=Card)
def set_text(sender, instance, **kwargs):
    if not instance.text and instance.data:
        instance.text = instance.data.get("text") or ""
