import json

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from peterbecom.plog.models import BlogComment


class BayesData(models.Model):
    id = models.AutoField(primary_key=True)
    pickle_data = models.BinaryField()
    options = models.JSONField()
    # Could be things like 'spam' or 'language'
    topic = models.CharField(max_length=100, default="comments")
    size = models.IntegerField()
    modified = models.DateTimeField(auto_now=True)

    def __repr__(self):
        return "<{}: {} (options={!r} size={})>".format(
            self.__class__.__name__,
            self.topic,
            json.dumps(self.options),
            format(self.size, ","),
        )


@receiver(pre_save, sender=BayesData)
def update_pickle_data_size(sender, instance, **kwargs):
    if not instance.size:
        instance.size = len(instance.pickle_data)


class BlogCommentTraining(models.Model):
    id = models.AutoField(primary_key=True)
    comment = models.OneToOneField(BlogComment, on_delete=models.CASCADE)
    bayes_data = models.ForeignKey(BayesData, on_delete=models.CASCADE)
    tag = models.CharField(max_length=100)
    modified = models.DateTimeField(auto_now=True)

    def __repr__(self):
        return "<{}: {} on {!r} in {!r}>".format(
            self.__class__.__name__, self.tag, self.song, self.bayes_data
        )
