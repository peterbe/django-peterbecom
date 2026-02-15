import datetime
import functools
import hashlib
import os
import random
import re
import string
import time
import unicodedata
import uuid
from collections import defaultdict

import bleach
from cachetools import TTLCache, cached
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import Count, Max, Q
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from pgvector.django import VectorField
from sorl.thumbnail import ImageField

from peterbecom.base.geo import ip_to_city
from peterbecom.base.models import CDNPurgeURL
from peterbecom.base.utils import generate_search_terms

from . import utils
from .utils import blog_post_url

# This is where we can cache counts of comments per blogitem id.
count_comments_cache = TTLCache(maxsize=1000, ttl=60)  # XXX increase TTL
count_approved_comments_cache = TTLCache(maxsize=1000, ttl=60)


class HTMLRenderingError(Exception):
    """When rendering Markdown or RsT generating invalid HTML."""


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.name)

    def __str__(self):
        return self.name

    @classmethod
    @functools.lru_cache(maxsize=1)
    def get_category_id_name_map(cls):
        return dict(Category.objects.values_list("id", "name"))


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def purge_get_category_id_name_map(sender, instance, **kwargs):
    Category.get_category_id_name_map.cache_clear()


class SearchTerm(models.Model):
    term = models.CharField(max_length=100, db_index=True)
    popularity = models.FloatField(default=0.0)
    add_date = models.DateTimeField(auto_now=True)
    index_version = models.IntegerField(default=0)

    class Meta:
        unique_together = ("term", "index_version")
        indexes = [
            GinIndex(
                name="plog_searchterm_term_gin_idx",
                fields=["term"],
                opclasses=["gin_trgm_ops"],
            ),
        ]


class SearchDoc(models.Model):
    oid = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    title_search_vector = SearchVectorField("title")
    text = models.TextField()
    text_search_vector = SearchVectorField("text")
    popularity = models.FloatField(default=0.0)
    date = models.DateTimeField()
    keywords = ArrayField(models.CharField(max_length=100), default=list)
    categories = ArrayField(models.CharField(max_length=100), default=list)

    title_embedding = VectorField(
        dimensions=768,
        null=True,
        blank=True,
    )

    text_embedding = VectorField(
        dimensions=768,
        null=True,
        blank=True,
    )

    # meta data
    add_date = models.DateTimeField(auto_now=True)
    source_modify_date = models.DateTimeField()
    index_version = models.IntegerField(default=0)

    class Meta:
        unique_together = ("oid", "index_version")
        indexes = [
            GinIndex(fields=["title_search_vector"]),
            GinIndex(fields=["text_search_vector"]),
            GinIndex(
                name="plog_searchdoc_title_gin_idx",
                fields=["title"],
                opclasses=["gin_trgm_ops"],
            ),
        ]


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
        return blog_post_url(self.oid)

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
            from random import choice
            from string import lowercase, uppercase

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

    # def to_search(self, **kwargs):
    #     doc = self.to_search_doc(**kwargs)
    #     assert self.id
    #     return BlogItemDoc(meta={"id": self.id}, **doc)

    def to_search_doc(self, **kwargs):
        if "all_categories" in kwargs:
            categories = kwargs["all_categories"].get(self.id, [])
            assert isinstance(categories, list), categories
        else:
            categories = [x.name for x in self.categories.all()]

        cleaned = bleach.clean(self.text_rendered, strip=True, tags=[]).strip()
        doc = {
            "id": self.id,
            "oid": self.oid,
            "title": self.title,
            "popularity": self.popularity or 0.0,
            "text": cleaned,
            "date": self.pub_date,
            "categories": categories,
            "keywords": self.proper_keywords,
            "modify_date": self.modify_date,
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
        iterator = cls._get_indexing_queryset()
        t0 = time.time()
        if ids_only:
            iterator = iterator.filter(id__in=ids_only)
        category_names = dict((x.id, x.name) for x in Category.objects.all())
        categories = defaultdict(list)
        for e in BlogItem.categories.through.objects.all():
            categories[e.blogitem_id].append(category_names[e.category_id])

        report_every = 100
        count = 0

        current_index_version = (
            SearchDoc.objects.aggregate(Max("index_version"))["index_version__max"] or 0
        )
        index_version = current_index_version + 1

        bulk: list[SearchDoc] = []
        for m in iterator:
            to_search_doc = m.to_search_doc(all_categories=categories)
            bulk.append(
                SearchDoc(
                    oid=to_search_doc["oid"],
                    title=to_search_doc["title"],
                    date=to_search_doc["date"],
                    text=to_search_doc["text"],
                    keywords=to_search_doc["keywords"],
                    popularity=to_search_doc["popularity"] or 0.0,
                    categories=to_search_doc["categories"],
                    index_version=index_version,
                    source_modify_date=to_search_doc["modify_date"],
                )
            )
            count += 1
            if verbose and not count % report_every:
                print(f"{count:,}")

        SearchDoc.objects.bulk_create(bulk)

        SearchDoc.objects.filter(index_version__lt=index_version).delete()

        SearchDoc.objects.all().update(
            title_search_vector=SearchVector("title", config="english"),
            text_search_vector=SearchVector("text", config="english"),
        )

        t1 = time.time()
        return count, t1 - t0, index_version

    @classmethod
    def _get_indexing_queryset(cls):
        return cls.objects.filter(archived__isnull=True, pub_date__lt=timezone.now())

    @classmethod
    def index_all_search_terms(cls, verbose=False):
        query_set = cls._get_indexing_queryset()
        t0 = time.time()
        count = 0
        search_terms = defaultdict(list)
        for title, popularity, keywords, text in query_set.values_list(
            "title", "popularity", "proper_keywords", "text"
        ):
            count += 1
            for search_term in generate_search_terms(title):
                if len(search_term) <= 1 and search_term in string.ascii_letters:
                    continue
                p = popularity or 0.0
                # The longer it is the lower the popularity score
                length = len(search_term.split())
                adjusted_popularity = p - max(0, p * 0.01 * length)
                search_terms[search_term].append(adjusted_popularity)

            for keyword in keywords:
                if len(keyword) <= 1 and keyword in string.ascii_letters:
                    continue
                # Some keywords are NOT present in the title or text.
                # That means if we suggested it and the user proceeds to search
                # it might not find anything.
                if re.findall(rf"\b{re.escape(keyword)}\b", text, re.I) or re.findall(
                    rf"\b{re.escape(keyword)}\b", title, re.I
                ):
                    p = popularity or 0.0
                    # Reduce it by 10% to make it ever so slightly less important
                    # that the term as it's derived from a title.
                    # A lot of keywords aren't actually present in the title,
                    # so it could be negatively surprising if the word works but
                    # only works because it's deep in the body.
                    search_terms[keyword.lower()].append(max(0, p * 0.9))

        current_index_version = (
            SearchTerm.objects.aggregate(Max("index_version"))["index_version__max"]
            or 0
        )
        index_version = current_index_version + 1

        report_every = 100
        count = 0

        bulk: list[SearchTerm] = []
        for term, popularities in search_terms.items():
            if len(term) < 2:
                continue
            bulk.append(
                SearchTerm(
                    term=term, popularity=sum(popularities), index_version=index_version
                )
            )
            count += 1
            if verbose and not count % report_every:
                print(f"{count:,}")

        SearchTerm.objects.bulk_create(bulk)

        SearchTerm.objects.filter(index_version__lt=index_version).delete()

        t1 = time.time()
        print(
            f"Bulk inserted {count:,} search terms in {t1 - t0:.2f} seconds. "
            f"Index version: {index_version}"
        )
        return count, t1 - t0, index_version


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

    def __str__(self):
        return f"{self.blogitem.oid} on {self.add_date}"


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
    highlighted = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(
                name="add_date_when_parent_null",
                fields=["add_date"],
                condition=Q(parent__isnull=True),
            ),
        ]

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


# These utility function is an optimization to avoid hitting the database.
# Comments are rarely added, edited, or deleted.
# But when they are, we specifically purge by the blogitem_id, which is the
# simple cache key in the memoization.
#
# Rough estimate is that counting, for example, the number of comments on the
# blogitem (with the most comments), takes 10-20 milliseconds. Reading from
# the in-memory cache is 0.01 milliseconds. So, about 1000x faster.


@cached(cache=count_comments_cache)
def count_approved_comments(blogitem_id):
    return BlogComment.objects.filter(blogitem=blogitem_id, approved=True).count()


@cached(cache=count_approved_comments_cache)
def count_approved_root_comments(blogitem_id):
    return BlogComment.objects.filter(
        blogitem__id=blogitem_id, approved=True, parent__isnull=True
    ).count()


@receiver(post_save, sender=BlogComment)
@receiver(post_delete, sender=BlogComment)
def purge_count_approved_comments(sender, instance, **kwargs):
    count_key = count_approved_comments.cache_key(instance.blogitem_id)
    count_approved_comments.cache.pop(count_key, None)

    count_root_key = count_approved_root_comments.cache_key(instance.blogitem_id)
    count_approved_root_comments.cache.pop(count_root_key, None)


@receiver(pre_save, sender=BlogComment)
def update_comment_rendered(sender, instance, **kwargs):
    instance.comment_rendered = sender.get_rendered_comment(instance.comment)


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
            urls.append(blog_post_url(blogitem.oid, page))
        else:
            urls.append(blog_post_url(blogitem.oid))

    if urls:
        CDNPurgeURL.add(urls)


@receiver(models.signals.post_save, sender=BlogItem)
def update_search_doc(sender, instance, **kwargs):
    if sender is BlogItem:
        if instance.archived or instance.pub_date > timezone.now():
            return

        as_search_doc = instance.to_search_doc()
        updated = SearchDoc.objects.filter(oid=instance.oid).update(
            title=as_search_doc["title"],
            date=as_search_doc["date"],
            text=as_search_doc["text"],
            keywords=as_search_doc["keywords"],
            popularity=as_search_doc["popularity"],
            categories=as_search_doc["categories"],
            source_modify_date=as_search_doc["modify_date"],
        )
        if not updated:
            current_index_version = (
                SearchTerm.objects.aggregate(Max("index_version"))["index_version__max"]
                or 0
            )
            SearchDoc.objects.create(
                oid=as_search_doc["oid"],
                title=as_search_doc["title"],
                date=as_search_doc["date"],
                text=as_search_doc["text"],
                keywords=as_search_doc["keywords"],
                popularity=as_search_doc["popularity"],
                categories=as_search_doc["categories"],
                source_modify_date=as_search_doc["modify_date"],
                index_version=current_index_version,
            )


@receiver(models.signals.pre_delete, sender=BlogItem)
def delete_from_search_doc(sender, instance, **kwargs):
    SearchDoc.objects.filter(oid=instance.oid).delete()


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


class SpamCommentSignature(models.Model):
    name = models.CharField(max_length=300, null=True)
    email = models.CharField(max_length=300, null=True)
    kills = models.PositiveIntegerField(default=0)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)


class BlogCommentClassification(models.Model):
    blogcomment = models.OneToOneField(
        BlogComment, null=True, on_delete=models.SET_NULL
    )
    text = models.TextField()
    classification = models.CharField(max_length=100)
    add_date = models.DateTimeField(auto_now_add=True)
    modify_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        truncated = f"{self.text[:80]}..." if len(self.text) > 80 else self.text
        return f"{self.classification!r} on {truncated!r}"
