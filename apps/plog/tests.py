import datetime
from django.core.urlresolvers import reverse
from django.test import TestCase
from apps.plog.models import BlogItem, BlogComment, Category
from apps.plog.utils import utc_now
from apps.redisutils import get_redis_connection


class PlogTestCase(TestCase):
    def setUp(self):
        redis = get_redis_connection()
        redis.flushdb()

    def test_blog_post_caching(self):
        blog = BlogItem.objects.create(
          oid='some-longish-test-post',
          title='TITLEX',
          text='BLABLABLA',
          display_format='structuredtext',
          pub_date=utc_now() - datetime.timedelta(seconds=10),
        )
        url = reverse('blog_post', args=[blog.oid])

        import apps.plog.views
        old_render = apps.plog.views.render
        from django.shortcuts import render as django_render
        render_counts = []
        def mocked_render(*a, **k):
            render_counts.append(1)
            return django_render(*a, **k)
        apps.plog.views.render = mocked_render
        try:
            response = self.client.get(url)
            self.assertTrue(blog.title in response.content)
            assert '0 comments' in response.content
            response = self.client.get(url)
            assert '0 comments' in response.content

            comment1 = BlogComment.objects.create(
              comment="textext",
              blogitem=blog,
              approved=True,
              add_date=utc_now() + datetime.timedelta(seconds=1),
            )
            response = self.client.get(url)
            assert '1 comment' in response.content
        finally:
            apps.plog.views.render = old_render

        assert len(render_counts) == 2
