from django.db import models
from django.db.models.signals import pre_save
from django.contrib.postgres.fields import ArrayField
from django.dispatch import receiver

from .search import lookup, NothingFoundError


class AWSProduct(models.Model):
    # Consider adding something like this:
    #
    #   CREATE INDEX awspa_awsproduct_keywords_idx
    #   ON awspa_awsproduct USING GIN(keywords);
    #
    # if this turns out to perform poorly.
    keywords = ArrayField(models.CharField(max_length=100), default=list)
    searchindex = models.CharField(max_length=100)
    # XXX Eventually, this should become unique
    asin = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField()
    disabled = models.BooleanField(default=False)
    title = models.CharField(max_length=300)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)
    # XXX Write a migration to get rid of this
    paapiv5 = models.BooleanField(default=True)
    # XXX Write a migration to get rid of this
    keyword = models.CharField(max_length=200, db_index=True)

    def __repr__(self):
        return "<{} {} {!r}{}>".format(
            self.__class__.__name__,
            self.asin,
            self.title[:50],
            "..." if len(self.title) > 50 else "",
        )

    def convert_to_paapiv5(self, raise_if_nothing_found=False):
        assert not self.paapiv5

        try:
            payload, errors = lookup(self.asin)
            if errors:
                raise NotImplementedError(errors)
        except NothingFoundError:
            if raise_if_nothing_found:
                raise
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
