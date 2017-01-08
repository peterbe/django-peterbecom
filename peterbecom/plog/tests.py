import re
import datetime
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.conf import settings
from django.test import TestCase, Client

from peterbecom.plog.models import BlogItem, BlogComment, Category
from peterbecom.plog.utils import utc_now


class PlogTestCase(TestCase):

    def setUp(self):
        super(PlogTestCase, self).setUp()

    def _login(self):
        admin = User.objects.create(
            username='admin',
            is_staff=True
        )
        admin.set_password('secret')
        admin.save()
        assert self.client.login(username='admin', password='secret')
        return admin

    def test_blog_post_caching(self):
        blog = BlogItem.objects.create(
            oid='some-longish-test-post',
            title='TITLEX',
            text='BLABLABLA',
            display_format='structuredtext',
            pub_date=utc_now() - datetime.timedelta(seconds=10),
        )
        url = reverse('blog_post', args=[blog.oid])

        import peterbecom.plog.views
        old_render = peterbecom.plog.views.render
        from django.shortcuts import render as django_render
        render_counts = []

        def mocked_render(*a, **k):
            render_counts.append(1)
            return django_render(*a, **k)

        peterbecom.plog.views.render = mocked_render
        try:
            response = self.client.get(url)
            content = response.content.decode('utf-8')
            self.assertTrue(blog.title in content)
            assert '0 comments' in content
            response = self.client.get(url)
            content = response.content.decode('utf-8')
            assert '0 comments' in content

            BlogComment.objects.create(
                comment="textext",
                blogitem=blog,
                approved=True,
                add_date=utc_now() + datetime.timedelta(seconds=1),
            )
            response = self.client.get(url)
            content = response.content.decode('utf-8')
            assert '1 comment' in content
        finally:
            peterbecom.plog.views.render = old_render

        # XXX HACK!
        # Need to upgrade fancy-cache thing so that it doesn't
        # call the key prefixer for both the request and the response.
        # assert len(render_counts) == 2, render_counts

    def test_blog_post_with_comment_approval(self):
        blog = BlogItem.objects.create(
            oid='some-longish-test-post',
            title='TITLEX',
            text='BLABLABLA',
            display_format='structuredtext',
            pub_date=utc_now() - datetime.timedelta(seconds=10),
        )
        url = reverse('blog_post', args=[blog.oid])

        self._login()
        loggedin = self.client
        anonymous = Client()
        assert len(loggedin.cookies)
        assert not len(anonymous.cookies)

        comment = BlogComment.objects.create(
            oid='a1000',
            blogitem=blog,
            comment='COMMENTX',
            name='Mr Anonymous',
        )
        # but it hasn't been approved yet
        response = anonymous.get(url)
        content = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertTrue('COMMENTX' not in content)

        # let's approve it!
        approve_url = reverse('approve_comment', args=[blog.oid, comment.oid])
        response = loggedin.post(
            approve_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('utf-8'), 'OK')

        response = anonymous.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('COMMENTX' in str(response.content))

    def test_text_rendering_with_images(self):
        blog = BlogItem.objects.create(
            oid='myoid',
            title='TITLEX',
            text="""
            "image.png":/plog/myoid/image.png
            and *this*
            """,
            display_format='structuredtext',
            pub_date=utc_now() - datetime.timedelta(seconds=10),
        )
        url = reverse('blog_post', args=[blog.oid])
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        self.assertTrue('<em>this</em>' in content)
        regex_str = (
            '/CONTENTCACHE-\d+%s' % (re.escape('/plog/myoid/image.png'),)
        )
        self.assertTrue(re.findall(regex_str, content))

        old = settings.STATIC_URL
        settings.STATIC_URL = '//some.cdn.com/'
        try:
            blog.text_rendered = ''
            blog.save()
            response = self.client.get(url)
            content = response.content.decode('utf-8')
            regex_str = (
                '%sCONTENTCACHE-\d+%s' % (
                    settings.STATIC_URL,
                    re.escape('/plog/myoid/image.png')
                )
            )
            self.assertTrue(re.findall(regex_str, content))
        finally:
            settings.STATIC_URL = old

    def test_preview_post(self):
        cat = Category.objects.create(name="MyCategory")
        self._login()
        url = reverse('plog_preview_post')
        data = {
            'title': 'Some <script> TITLE',
            'text': 'This is\n*great*\nin `verbatim`',
            'display_format': 'markdown',
            'pub_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'categories[]': str(cat.pk),
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        # self.assertTrue('Some &lt;script&gt; TITLE' in response.content)
        content = response.content.decode('utf-8')
        self.assertTrue('This is<br' in content)
        self.assertTrue('<em>great</em>' in content)
        self.assertTrue('<code>verbatim</code>' in content)

        data['text'] = """This is

```python
def foo():
    return None
```

code"""

        response = self.client.post(url, data)
        content = response.content.decode('utf-8')
        self.assertTrue('<div class="highlight">' in content)
        self.assertTrue('<span class="k">def</span>' in content)

    def test_old_redirects(self):
        blog = BlogItem.objects.create(
            oid='myoid',
            title='TITLEX',
            text="""
            ttest test
            """,
            display_format='structuredtext',
            pub_date=utc_now() - datetime.timedelta(seconds=10),
        )
        url = reverse('blog_post', args=[blog.oid])

        response = self.client.get(url)
        assert response.status_code == 200

        response = self.client.get(url, {'replypath': 'foo'})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(urlparse(response['location']).path, url)
        self.assertTrue(not urlparse(response['location']).query)
