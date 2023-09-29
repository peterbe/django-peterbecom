import datetime
import functools
import hashlib
import os
import random
import time
import unicodedata
import uuid
from collections import defaultdict

import bleach
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.urls import reverse
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl.connections import connections
from sorl.thumbnail import ImageField

from peterbecom.base.geo import ip_to_city
from peterbecom.base.utils import send_pulse_message
from peterbecom.base.search import es_retry
from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc
from peterbecom.base.models import CDNPurgeURL

from . import utils


class HTMLRenderingError(Exception):
    """When rendering Markdown or RsT generating invalid HTML."""


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.name)

    def __str__(self):
        return self.name


def _upload_path_tagged(tag, instance, filename):
    if isinstance(filename, str):
        filename = unicodedata.normalize("NFD", filename).encode("ascii", "ignore")
    now = datetime.datetime.utcnow()
    path = os.path.join(now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
    hashed_filename = hashlib.md5(
        filename + str(now.microsecond).encode("utf-8")
    ).hexdigest()
    __, extension = os.path.splitext(str(filename))
    return os.path.join(tag, path, hashed_filename + extension)


def _upload_to_blogitem(instance, filename):
    return _upload_path_tagged("blogitems", instance, filename)


class BlogItem(models.Model):
    oid = models.CharField(max_length=100, db_index=True, unique=True)
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
    # this will be renamed to "keywords" later
    proper_keywords = ArrayField(models.CharField(max_length=100), default=list)
    plogrank = models.FloatField(null=True)
    codesyntax = models.CharField(max_length=20, blank=True)
    disallow_comments = models.BooleanField(default=False)
    hide_comments = models.BooleanField(default=False)
    modify_date = models.DateTimeField(default=utils.utc_now)
    screenshot_image = ImageField(upload_to=_upload_to_blogitem, null=True)
    open_graph_image = models.CharField(max_length=400, null=True)
    popularity = models.FloatField(default=0.0, null=True)
    archived = models.DateTimeField(null=True)

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.oid)

    def get_absolute_url(self):
        return reverse("blog_post", args=(self.oid,))

    @property
    def rendered(self):
        return self._render()

    def _render(self, refresh=False):
        if not self.text_rendered or refresh:
            self.text_rendered = self.__class__.render(
                self.text, self.display_format, self.codesyntax
            )
            self.save()
        return self.text_rendered

    @classmethod
    def render(cls, text, display_format, codesyntax, strict=False):
        if display_format == "structuredtext":
            text_rendered = utils.stx_to_html(text, codesyntax)
        else:
            text_rendered = utils.markdown_to_html(text)
        if strict:
            bad = '<div class="highlight"></p>'
            if bad in text_rendered:
                lines = []
                for i, line in enumerate(text_rendered.splitlines()):
                    if bad in line:
                        lines.append(i + 1)
                raise HTMLRenderingError(
                    "Rendered HTML contains invalid HTML (line: {})".format(
                        ", ".join([str(x) for x in lines])
                    )
                )
        return text_rendered

    def count_comments(self, refresh=False):
        cache_key = "nocomments:%s" % self.pk
        count = cache.get(cache_key)
        if count is None or refresh:
            count = self._count_comments()
            cache.set(cache_key, count, 60 * 60 * 24)
        return count

    def _count_comments(self):
        return BlogComment.objects.filter(blogitem=self, approved=True).count()

    def __str__(self):
        return self.title

    def get_or_create_inbound_hashkey(self):
        cache_key = "inbound_hashkey_%s" % self.pk
        value = cache.get(cache_key)
        if not value:
            value = self._new_inbound_hashkey(5)
            cache.set(cache_key, value, 60 * 60 * 60)
            hash_cache_key = "hashkey-%s" % value
            cache.set(hash_cache_key, self.pk, 60 * 60 * 60)
        return value

    def _new_inbound_hashkey(self, length):
        def mk():
            from string import lowercase, uppercase
            from random import choice

            s = choice(list(uppercase))
            while len(s) < length:
                s += choice(list(lowercase + "012345789"))
            return s

        key = mk()
        while cache.get("hashkey-%s" % key):
            key = mk()
        return key

    @classmethod
    def get_by_inbound_hashkey(cls, hashkey):
        cache_key = "hashkey-%s" % hashkey
        value = cache.get(cache_key)
        if not value:
            raise cls.DoesNotExist("not found")
        return cls.objects.get(pk=value)

    def to_search(self, **kwargs):
        doc = self.to_search_doc(**kwargs)
        assert self.id
        return BlogItemDoc(meta={"id": self.id}, **doc)

    def to_search_doc(self, **kwargs):
        if "all_categories" in kwargs:
            categories = kwargs["all_categories"].get(self.id, [])
            assert isinstance(categories, list), categories
        else:
            categories = [x.name for x in self.categories.all()]

        cleaned = bleach.clean(self.text_rendered, strip=True, tags=[])

        doc = {
            "id": self.id,
            "oid": self.oid,
            "title": self.title,
            "title_autocomplete": self.title,
            "popularity": self.popularity or 0.0,
            "text": cleaned,
            "pub_date": self.pub_date,
            "categories": categories,
            "keywords": self.proper_keywords,
        }
        return doc

    def get_all_keywords(self):
        all_keywords = [x.name.lower() for x in self.categories.all()]
        for keyword in self.proper_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in all_keywords:
                all_keywords.append(keyword_lower)

        return all_keywords

    @classmethod
    def index_all_blogitems(cls, ids_only=None, verbose=False):
        iterator = cls.objects.all()
        if ids_only:
            iterator = iterator.filter(id__in=ids_only)
        category_names = dict((x.id, x.name) for x in Category.objects.all())
        categories = defaultdict(list)
        for e in BlogItem.categories.through.objects.all():
            categories[e.blogitem_id].append(category_names[e.category_id])

        es = connections.get_connection()
        report_every = 100
        count = 0
        t0 = time.time()
        for success, doc in parallel_bulk(
            es,
            (m.to_search(all_categories=categories).to_dict(True) for m in iterator),
            index=settings.ES_BLOG_ITEM_INDEX,
        ):
            if not success:
                print("NOT SUCCESS!", doc)
            count += 1
            if verbose and not count % report_every:
                print(f"{count:,}")
        t1 = time.time()
        return count, t1 - t0


class BlogItemTotalHits(models.Model):
    blogitem = models.OneToOneField(BlogItem, db_index=True, on_delete=models.CASCADE)
    total_hits = models.IntegerField(default=0)
    modify_date = models.DateTimeField(auto_now=True)

    @classmethod
    def update_all(cls):
        count_records = 0
        qs = BlogItemHit.objects.all()
        with transaction.atomic():
            existing = {
                x["blogitem_id"]: x["total_hits"]
                for x in BlogItemTotalHits.objects.all().values(
                    "blogitem_id", "total_hits"
                )
            }
            for aggregate in qs.values("blogitem_id").annotate(
                count=Count("blogitem_id")
            ):
                if aggregate["blogitem_id"] not in existing:
                    cls.objects.create(
                        blogitem_id=aggregate["blogitem_id"],
                        total_hits=aggregate["count"],
                    )
                elif existing[aggregate["blogitem_id"]] != aggregate["count"]:
                    cls.objects.filter(blogitem_id=aggregate["blogitem_id"]).update(
                        total_hits=aggregate["count"]
                    )
                count_records += 1
        return count_records


class BlogItemDailyHitsExistingError(Exception):
    """When you're trying to roll up an aggregate on date that is already rolled up."""


class BlogItemDailyHits(models.Model):
    blogitem = models.ForeignKey(BlogItem, on_delete=models.CASCADE)
    date = models.DateField()
    total_hits = models.IntegerField(default=0)
    modify_date = models.DateTimeField(auto_now=True)

    @classmethod
    def rollup_date(cls, date, refresh=False):
        assert isinstance(date, datetime.datetime), type(date)
        start_of_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date = start_of_date.date()
        existing_qs = BlogItemDailyHits.objects.filter(date=date)
        if refresh:
            existing_qs.delete()
        elif existing_qs.exists():
            raise BlogItemDailyHitsExistingError(date)

        one_day = datetime.timedelta(days=1)
        qs = BlogItemHit.objects.filter(
            add_date__gte=start_of_date, add_date__lt=start_of_date + one_day
        )
        bulk = []

        sum_count = 0
        for agg in qs.values("blogitem").annotate(count=Count("blogitem")):
            count = agg["count"]
            sum_count += count
            bulk.append(
                BlogItemDailyHits(
                    blogitem_id=agg["blogitem"], date=date, total_hits=count
                )
            )
        BlogItemDailyHits.objects.bulk_create(bulk)
        return sum_count, len(bulk)


class BlogItemHit(models.Model):
    """This started being used in July 2017"""

    blogitem = models.ForeignKey(BlogItem, on_delete=models.CASCADE)
    add_date = models.DateTimeField(auto_now_add=True)
    remote_addr = models.GenericIPAddressField(null=True)
    http_referer = models.URLField(max_length=450, null=True)
    page = models.PositiveIntegerField(null=True)


class BlogComment(models.Model):
    oid = models.CharField(max_length=100, db_index=True, unique=True)
    blogitem = models.ForeignKey(BlogItem, null=True, on_delete=models.CASCADE)
    parent = models.ForeignKey("BlogComment", null=True, on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    auto_approved = models.BooleanField(default=False)
    comment = models.TextField()
    comment_rendered = models.TextField(blank=True, null=True)
    add_date = models.DateTimeField(default=utils.utc_now)
    modify_date = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=300, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    geo_lookup = models.JSONField(null=True)

    # def __repr__(self):
    #     return "<%s: %s %r (%sapproved)>" % (
    #         self.__class__.__name__,
    #         self.id,
    #         self.oid + " " + self.comment[:20],
    #         not self.approved and "not" or "",
    #     )

    def __str__(self):
        return "{} {!r} ({})".format(
            self.id,
            self.oid + " " + self.comment[:20],
            "approved" if self.approved else "not approved",
        )

    @classmethod
    def get_rendered_comment(cls, comment):
        return utils.render_comment_text(comment)

    @property
    def rendered(self):
        if not self.comment_rendered:
            print("DEPRECATED! THIS SHOULDN'T BE USED ANY MORE")
            self.comment_rendered = self.__class__.get_rendered_comment(self.comment)
            self.save()
        return self.comment_rendered

    @classmethod
    def next_oid(cls):
        return "c" + uuid.uuid4().hex[:6]

    def get_absolute_url(self):
        return self.blogitem.get_absolute_url() + "#%s" % self.oid

    def correct_blogitem_parent(self):
        assert self.blogitem is None
        if self.parent.blogitem is None:
            self.parent.correct_blogitem_parent()
        self.blogitem = self.parent.blogitem
        self.save()

    def to_search(self, **kwargs):
        doc = self.to_search_doc(**kwargs)
        return BlogCommentDoc(meta={"id": self.id}, **doc)

    def to_search_doc(self, **kwargs):
        doc = {
            "id": self.id,
            "oid": self.oid,
            "blogitem_id": self.blogitem_id,
            "approved": self.approved,
            "add_date": self.add_date,
            "comment": self.comment_rendered or self.comment,
            "popularity": self.blogitem.popularity or 0.0,
        }
        return doc

    def create_geo_lookup(self):
        found = False
        if self.ip_address:
            found = ip_to_city(self.ip_address)
            print(repr(self.ip_address), "=>", found)
            if found:
                self.__class__.objects.filter(id=self.id).update(geo_lookup=found)

        return found

    @classmethod
    def index_all_blogcomments(cls, verbose=False):
        iterator = cls.objects.all().select_related("blogitem")

        es = connections.get_connection()
        report_every = 1000
        count = 0
        t0 = time.time()
        for success, doc in parallel_bulk(
            es,
            (m.to_search().to_dict(True) for m in iterator),
            index=settings.ES_BLOG_COMMENT_INDEX,
        ):
            if not success:
                print("NOT SUCCESS!", doc)
            count += 1
            if verbose and not count % report_every:
                print(f"{count:,}")
        t1 = time.time()
        return count, t1 - t0


@receiver(pre_save, sender=BlogComment)
def update_comment_rendered(sender, instance, **kwargs):
    instance.comment_rendered = sender.get_rendered_comment(instance.comment)


@receiver(post_save, sender=BlogComment)
def send_search_result_pulse_message(sender, instance, **kwargs):
    if kwargs.get("created"):
        send_pulse_message(
            {
                "commented": {
                    "oid": instance.oid,
                    "blogitem": {
                        "oid": instance.blogitem.oid,
                        "title": instance.blogitem.title,
                    },
                    "name": instance.name,
                    "email": instance.email,
                }
            }
        )


def _uploader_dir(instance, filename):
    def fp(filename):
        return os.path.join("plog", instance.blogitem.oid, filename)

    a, b = os.path.splitext(filename)
    if isinstance(a, str):
        a = a.encode("ascii", "ignore")
    a = hashlib.md5(a).hexdigest()[:10]
    filename = "%s.%s%s" % (a, int(time.time()), b)
    return fp(filename)


class BlogFile(models.Model):
    blogitem = models.ForeignKey(BlogItem, on_delete=models.CASCADE)
    file = models.FileField(upload_to=_uploader_dir)
    title = models.CharField(max_length=300, null=True, blank=True)
    add_date = models.DateTimeField(default=utils.utc_now)
    modify_date = models.DateTimeField(default=utils.utc_now)

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.blogitem.oid)


def random_string(length):
    pool = list("abcdefghijklmnopqrstuvwxyz")
    pool.extend([x.upper() for x in pool])
    pool.extend("0123456789")
    random.shuffle(pool)
    return "".join(pool[:length])


# XXX Can this be entirely deleted now?!
class OneTimeAuthKey(models.Model):
    key = models.CharField(max_length=16, default=functools.partial(random_string, 16))
    blogitem = models.ForeignKey(BlogItem, on_delete=models.CASCADE)
    blogcomment = models.ForeignKey(BlogComment, null=True, on_delete=models.CASCADE)
    used = models.DateTimeField(null=True)
    add_date = models.DateTimeField(auto_now_add=True)


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
    cache_key = "nocomments:%s" % pk
    cache.delete(cache_key)


@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_latest_comment_add_dates(sender, instance, **kwargs):
    cache_key = "latest_comment_add_date"
    cache.delete(cache_key)

    if sender is BlogItem:
        oid = instance.oid
    elif sender is BlogComment:
        oid = instance.blogitem.oid
    else:
        raise NotImplementedError(sender)
    cache_key = "latest_comment_add_date:%s" % (
        hashlib.md5(oid.encode("utf-8")).hexdigest()
    )
    cache.delete(cache_key)


@receiver(post_save, sender=BlogItem)
def invalidate_latest_post_modify_date(sender, instance, **kwargs):
    assert sender is BlogItem
    cache_key = "latest_post_modify_date"
    cache.delete(cache_key)


@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_publicapi_blogitem_by_oid(sender, instance, **kwargs):
    if sender is BlogItem:
        oid = instance.oid
    elif sender is BlogComment:
        oid = instance.blogitem.oid
    else:
        raise NotImplementedError(sender)

    pages = settings.MAX_BLOGCOMMENT_PAGES if oid == "blogitem-040601-1" else 1
    for i in range(1, pages + 1):
        cache_key = f"publicapi_blogitem_{oid}:{i}"
        if cache.get(cache_key):
            print(f"Purged publicapi cache key {cache_key!r}")
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
    cache_key = "latest_comment_add_date:%s" % (
        hashlib.md5(oid.encode("utf-8")).hexdigest()
    )
    cache.delete(cache_key)


@receiver(pre_save, sender=BlogFile)
@receiver(pre_save, sender=BlogItem)
@receiver(pre_save, sender=BlogComment)
def update_modify_date(sender, instance, **kwargs):
    if getattr(instance, "_modify_date_set", False):
        return
    if sender is BlogItem or sender is BlogFile:
        instance.modify_date = utils.utc_now()
    elif sender is BlogComment:
        if instance.blogitem and instance.approved:
            instance.blogitem.modify_date = utils.utc_now()
            instance.blogitem.save()
    else:
        raise NotImplementedError(sender)


@receiver(post_save, sender=BlogComment)
@receiver(post_save, sender=BlogItem)
def invalidate_cdn_urls(sender, instance, **kwargs):
    if kwargs["raw"]:
        return
    urls = []
    if sender is BlogItem:
        blogitem = instance
    elif sender is BlogComment:
        # Only invalidate if the comment is approved!
        if not instance.approved:
            return
        blogitem = instance.blogitem
    else:
        raise NotImplementedError(sender)

    comment_count = blogitem.count_comments()
    pages = comment_count // settings.MAX_RECENT_COMMENTS
    for page in range(1, pages + 2):
        if page >= settings.MAX_BLOGCOMMENT_PAGES:
            break
        if page > 1:
            urls.append(reverse("blog_post", args=[blogitem.oid, page]))
        else:
            urls.append(reverse("blog_post", args=[blogitem.oid]))

    if urls:
        CDNPurgeURL.add(urls)


@receiver(models.signals.post_save, sender=BlogItem)
@receiver(models.signals.post_save, sender=BlogComment)
def update_es(sender, instance, **kwargs):
    if sender is BlogComment:
        if not instance.approved:
            return
    doc = instance.to_search()
    es_retry(doc.save)


@receiver(models.signals.pre_delete, sender=BlogItem)
@receiver(models.signals.pre_delete, sender=BlogComment)
def delete_from_es(sender, instance, **kwargs):
    doc = instance.to_search()
    es_retry(doc.delete, _ignore_not_found=True)


class SpamCommentPattern(models.Model):
    pattern = models.CharField(max_length=200)
    is_regex = models.BooleanField(default=False)
    is_url_pattern = models.BooleanField(default=False)
    kills = models.PositiveIntegerField(default=0)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("pattern", "is_regex", "is_url_pattern")

    def __str__(self):
        return (
            "{!r}{}{}".format(
                self.pattern,
                self.is_regex and " (regex)" or "",
                self.is_url_pattern and " (url pattern)" or "",
            )
        ).strip()
