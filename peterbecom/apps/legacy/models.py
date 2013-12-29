from django.db import models

class LegacyBlogcomment(models.Model):
    oid = models.CharField(max_length=300)
    parent_oid = models.CharField(max_length=300)
    root = models.IntegerField(null=True, blank=True)
    approved = models.IntegerField(null=True, blank=True)
    comment = models.TextField()
    add_date = models.DateTimeField()
    name = models.CharField(max_length=300)
    email = models.CharField(max_length=600)
    class Meta:
        db_table = u'blogcomments'

class LegacyBlogitem(models.Model):
    oid = models.CharField(max_length=300)
    title = models.CharField(max_length=600)
    alias = models.CharField(max_length=600, blank=True)
    bookmark = models.IntegerField()
    text = models.TextField()
    summary = models.TextField()
    url = models.CharField(max_length=600, blank=True)
    pub_date = models.DateTimeField()
    display_format = models.CharField(max_length=60)
    itemcategories = models.CharField(max_length=600)
    keywords = models.CharField(max_length=1500)
    relatedids = models.CharField(max_length=600)
    plogrank = models.FloatField(null=True, blank=True)
    codesyntax_display_format = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = u'blogitems'
