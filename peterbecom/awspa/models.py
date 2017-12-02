from django.db import models
from django.contrib.postgres.fields import JSONField


class AWSProduct(models.Model):
    keyword = models.CharField(max_length=200, db_index=True)
    searchindex = models.CharField(max_length=100)
    asin = models.CharField(max_length=100, db_index=True)
    payload = JSONField()
    title = models.CharField(max_length=300)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('keyword', 'asin', 'searchindex')

    def __repr__(self):
        return '<{} {} {!r}>'.format(
            self.__class__.__name__,
            self.asin,
            self.title[:70]
        )
