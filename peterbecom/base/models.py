from django.db import models

from jsonfield import JSONField


class CommandRun(models.Model):
    command = models.CharField(max_length=100)
    app = models.CharField(max_length=100)
    duration = models.DurationField()
    notes = models.TextField(null=True)
    exception = models.TextField(null=True)
    options = JSONField(default={}, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __repr__(self):
        return '<{}: {!r}{}>'.format(
            self.__class__.__name__,
            self.command,
            self.exception and ' (Errored)' or '',
        )
