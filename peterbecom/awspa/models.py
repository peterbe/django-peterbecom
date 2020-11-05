from django.db import models
from django.contrib.postgres.fields import ArrayField


class AWSProduct(models.Model):
    keywords = ArrayField(models.CharField(max_length=100), default=list)
    searchindex = models.CharField(max_length=100)
    # XXX Eventually, this should become unique
    asin = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    disabled = models.BooleanField(default=False)
    title = models.CharField(max_length=300)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)

    def __repr__(self):
        return "<{} {} {!r}{}>".format(
            self.__class__.__name__,
            self.asin,
            self.title[:50],
            "..." if len(self.title) > 50 else "",
        )
