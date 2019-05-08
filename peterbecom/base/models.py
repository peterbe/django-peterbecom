from django.db import models

from jsonfield import JSONField as LegacyJSONField
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db.models.signals import pre_save
from django.dispatch import receiver


class CommandRun(models.Model):
    app = models.CharField(max_length=100)
    command = models.CharField(max_length=100)
    duration = models.DurationField()
    notes = models.TextField(null=True)
    exception = models.TextField(null=True)
    options = LegacyJSONField(default={}, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __repr__(self):
        return "<{}: {!r} {!r}{}>".format(
            self.__class__.__name__,
            self.app,
            self.command,
            self.exception and " (Errored)" or "",
        )


class PostProcessing(models.Model):
    filepath = models.CharField(max_length=400)
    url = models.URLField(max_length=400, db_index=True)
    original_url = models.URLField(max_length=400, null=True)
    duration = models.DurationField(null=True)
    notes = ArrayField(models.CharField(max_length=400), default=list)
    exception = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    previous = models.ForeignKey(
        "self",
        null=True,
        related_name="postprocessing",
        on_delete=models.CASCADE,
        db_index=False,
    )

    @classmethod
    def ongoing(cls):
        return cls.objects.filter(exception__isnull=True, duration__isnull=True)


@receiver(pre_save, sender=PostProcessing)
def set_previous(sender, instance, **kwargs):
    qs = PostProcessing.objects.filter(url=instance.url)
    if instance.id:
        qs = qs.exclude(id=instance.id)
    for previous in qs.order_by("-created")[:1]:
        instance.previous = previous


@receiver(pre_save, sender=PostProcessing)
def truncate_long_notes(sender, instance, **kwargs):
    for i, note in enumerate(instance.notes):
        if len(note) > 400:
            print(
                "WARNING! Note ({}) was too long [{}] ({!r})".format(i, len(note), note)
            )
            instance.notes[i] = note[:400]


class SearchResult(models.Model):
    q = models.CharField(max_length=400)
    original_q = models.CharField(max_length=400, null=True)
    documents_found = models.PositiveIntegerField()
    search_time = models.DurationField()
    search_times = JSONField(default=dict)
    search_terms = ArrayField(
        ArrayField(models.CharField(max_length=400), size=2, default=list), default=list
    )
    keywords = JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
