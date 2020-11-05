from django.db import models


class Minimization(models.Model):
    url = models.URLField()
    result = models.JSONField(null=True)
    error = models.JSONField(null=True)
    time_took = models.FloatField()
    add_date = models.DateTimeField(auto_now_add=True)
