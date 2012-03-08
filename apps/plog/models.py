import time
import os
import uuid
import datetime
from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from . import utils


class ArrayField(models.CharField):

    __metaclass__ = models.SubfieldBase
    description = "basic field for storing string arrays"

    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 200)
        super(ArrayField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, list):
            return value

        return value.split('|')

    def get_prep_value(self, value):
        return '|'.join(value)


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, self.name)

    def __unicode__(self):
        return self.name


class BlogItem(models.Model):
    """
    Indexes executed for this:

        CREATE INDEX plog_blogitem_text_eng_idx ON plog_blogitem
        USING gin(to_tsvector('english', text));

        CREATE INDEX plog_blogitem_title_eng_idx ON plog_blogitem
        USING gin(to_tsvector('english', title));

        REINDEX TABLE plog_blogitem;


    """
    oid = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=200)
    alias = models.CharField(max_length=200, null=True)
    bookmark = models.BooleanField(default=False)
    text = models.TextField()
    text_rendered = models.TextField(blank=True)
    summary = models.TextField()
    url = models.URLField(null=True)
    pub_date = models.DateTimeField(db_index=True)
    display_format = models.CharField(max_length=20)
    categories = models.ManyToManyField(Category)
    keywords = ArrayField(max_length=500)
    plogrank = models.FloatField(null=True)
    codesyntax = models.CharField(max_length=20, blank=True)
    disallow_comments = models.BooleanField(default=False)
    hide_comments = models.BooleanField(default=False)
    modify_date = models.DateTimeField(default=utils.utc_now)

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, self.oid)

    @models.permalink
    def get_absolute_url(self):
        return ('blog_post', [self.oid])

    @property
    def rendered(self):
        return self._render()

    def _render(self, refresh=False):
        if not self.text_rendered or refresh:
            if self.display_format == 'structuredtext':
                self.text_rendered = utils.stx_to_html(self.text, self.codesyntax)
            else:
                self.text_rendered = utils.markdown_to_html(self.text, self.codesyntax)
            self.text_rendered = utils.cache_prefix_files(self.text_rendered)
            self.save()
        return self.text_rendered

    def count_comments(self):
        cache_key = 'nocomments:%s' % self.pk
        count = cache.get(cache_key)
        if count is None:
            count = self._count_comments()
            cache.set(cache_key, count, 60 * 60 * 24)
        return count

    def _count_comments(self):
        return BlogComment.objects.filter(blogitem=self, approved=True).count()

    def __unicode__(self):
        return self.title


class BlogComment(models.Model):
    """
    Indexes executed for this:

        CREATE INDEX plog_blogcomment_comment_eng_idx ON plog_blogcomment
        USING gin(to_tsvector('english', comment));

        REINDEX TABLE plog_blogcomment;

    """

    oid = models.CharField(max_length=100, db_index=True)
    blogitem = models.ForeignKey(BlogItem, null=True)
    parent = models.ForeignKey('BlogComment', null=True)
    approved = models.BooleanField(default=False)
    comment = models.TextField()
    comment_rendered = models.TextField(blank=True, null=True)
    add_date = models.DateTimeField(default=utils.utc_now)
    name = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)
    ip_address = models.IPAddressField(blank=True, null=True)
    akismet_pass = models.NullBooleanField(null=True)

    def __repr__(self):
        return ('<%s: %r (%sapproved)>' %
                (self.__class__.__name__, self.oid + ' ' +self.comment[:20],
                 self.approved and '' or 'not '))

    @property
    def rendered(self):
        if not self.comment_rendered:
            self.comment_rendered = utils.render_comment_text(self.comment)
            self.save()
        return self.comment_rendered

    @classmethod
    def next_oid(cls):
        return 'c' + uuid.uuid4().hex[:6]

    def get_absolute_url(self):
        return self.blogitem.get_absolute_url() + '#%s' % self.oid

    def correct_blogitem_parent(self):
        assert self.blogitem is None
        if self.parent.blogitem is None:
            self.parent.correct_blogitem_parent()
        self.blogitem = self.parent.blogitem
        self.save()


def _uploader_dir(instance, filename):
    def fp(filename):
        return os.path.join('peterbecom/static',
                            'plog',
                            instance.blogitem.oid,
                            filename)
    a, b = os.path.splitext(filename)
    filename = '%s.%s%s' % (a, int(time.time()), b)
    return fp(filename)


class BlogFile(models.Model):
    blogitem = models.ForeignKey(BlogItem)
    file = models.FileField(upload_to=_uploader_dir)
    add_date = models.DateTimeField(default=utils.utc_now)
    modify_date = models.DateTimeField(default=utils.utc_now)

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, self.blogitem.oid)


@receiver(pre_delete, sender=BlogComment)
@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_blogitem_comment_count(sender, instance, **kwargs):
    if sender is BlogItem:
        pk = instance.pk
    elif sender is BlogComment:
        if instance.blogitem is None:
            if not instance.parent:  # legacy
                return
            instance.correct_blogitem_parent()  # legacy
        pk = instance.blogitem_id
    else:
        raise NotImplementedError(sender)
    cache_key = 'nocomments:%s' % pk
    cache.delete(cache_key)


#@receiver(pre_delete, sender=BlogComment)
@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_latest_comment_add_dates(sender, instance, **kwargs):
    cache_key = 'latest_comment_add_date'
    cache.delete(cache_key)

    if sender is BlogItem:
        pk = instance.pk
    elif sender is BlogComment:
        if instance.blogitem is None:
            instance.correct_blogitem_parent()  # legacy
        pk = instance.blogitem_id
    else:
        raise NotImplementedError(sender)
    cache_key = 'latest_comment_add_date:%s' % pk
    cache.delete(cache_key)


@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_latest_comment_add_date_by_oid(sender, instance, **kwargs):
    if sender is BlogItem:
        oid = instance.oid
    elif sender is BlogComment:
        oid = instance.blogitem.oid
    else:
        raise NotImplementedError(sender)
    cache_key = 'latest_comment_add_date:%s' % oid
    cache.delete(cache_key)


@receiver(pre_save, sender=BlogFile)
@receiver(pre_save, sender=BlogComment)
@receiver(pre_save, sender=BlogItem)
def update_modify_date(sender, instance, **kwargs):
    if getattr(instance, '_modify_date_set', False):
        return
    if sender is BlogItem or sender is BlogFile:
        instance.modify_date = utils.utc_now()
    elif sender is BlogComment:
        if instance.blogitem:
            instance.blogitem.modify_date = utils.utc_now()
    else:
        raise NotImplementedError(sender)
