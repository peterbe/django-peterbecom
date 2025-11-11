import hashlib
import json

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver


class LLMCall(models.Model):
    id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=255)
    messages = models.JSONField()
    message_hash = models.CharField(max_length=255, default="")
    temperature = models.IntegerField(null=True)
    response = models.JSONField()
    model = models.CharField(max_length=255)
    error = models.TextField(blank=True, null=True)
    attempts = models.IntegerField(default=0)
    took_seconds = models.FloatField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    @classmethod
    def make_message_hash(cls, messages):
        as_json = json.dumps(messages)
        hash = hashlib.sha256(as_json.encode("utf-8"))
        return hash.hexdigest()

    def __str__(self):
        return f"LLMCall(id={self.id}, status={self.status}, model={self.model}, error={self.error})"


@receiver(pre_save, sender=LLMCall)
def set_message_hash(sender, instance, **kwargs):
    if not instance.message_hash:
        instance.message_hash = sender.make_message_hash(instance.messages)
