from django.db import models
from django.db.models.signals import pre_save
from django.contrib.postgres.fields import JSONField
from django.dispatch import receiver

from .search import lookup, NothingFoundError


class AWSProduct(models.Model):
    keyword = models.CharField(max_length=200, db_index=True)
    searchindex = models.CharField(max_length=100)
    asin = models.CharField(max_length=100, db_index=True)
    payload = JSONField()
    disabled = models.BooleanField(default=False)
    title = models.CharField(max_length=300)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)
    paapiv5 = models.BooleanField(default=False)

    class Meta:
        unique_together = ("keyword", "asin", "searchindex")

    def __repr__(self):
        extra = ""
        if not self.paapiv5:
            extra += " (not paapiv5)"
        return "<{} {} {!r}{}>".format(
            self.__class__.__name__, self.asin, self.title[:50], extra
        )

    def convert_to_paapiv5(self):
        assert not self.paapiv5

        try:
            payload, errors = lookup(self.asin)
            if errors:
                raise NotImplementedError(errors)
        except NothingFoundError:
            self.disabled = True
            self.save()
        else:
            assert payload
            self.payload = payload
            self.paapiv5 = True
            self.save()


@receiver(pre_save, sender=AWSProduct)
def lowercase_keyword(sender, instance, **kwargs):
    instance.keyword = instance.keyword.lower()
