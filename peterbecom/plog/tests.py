import datetime
from urllib.parse import urlparse

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, BlogItemHit


@pytest.mark.django_db
def test_blog_post_caching(client):
    blog = BlogItem.objects.create(
        oid="some-longish-test-post",
        title="TITLEX",
        text="BLABLABLA",
        display_format="structuredtext",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    url = reverse("blog_post", args=[blog.oid])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert blog.title in content
    assert "0 comments" in content

    BlogComment.objects.create(
        comment="textext",
        blogitem=blog,
        approved=True,
        add_date=timezone.now() + datetime.timedelta(seconds=1),
    )
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "1 comment" in content


@pytest.mark.django_db
def test_old_redirects(client):
    blog = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="""
        ttest test
        """,
        display_format="structuredtext",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    url = reverse("blog_post", args=[blog.oid])

    response = client.get(url)
    assert response.status_code == 200

    response = client.get(url, {"replypath": "foo"})
    assert response.status_code == 301
    assert urlparse(response["location"]).path == url
    assert not urlparse(response["location"]).query


@pytest.mark.django_db
def test_blog_post_ping(client):
    blog = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="""
        ttest test
        """,
        display_format="structuredtext",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    url = reverse("blog_post_ping", args=[blog.oid])
    response = client.get(url)
    assert response.status_code == 405
    response = client.put(url)
    assert response.status_code == 200
    assert response.json()["ok"]

    hit, = BlogItemHit.objects.all()
    assert hit.blogitem == blog


@pytest.mark.django_db
def test_blog_post_with_newline_request_path(client):
    url = reverse("blog_post", args=["myoid"])
    response = client.get(url + "\n")
    assert response.status_code == 301
    assert urlparse(response["location"]).path == url

    response = client.get(url + "\nsomething")
    assert response.status_code == 301
    assert urlparse(response["location"]).path == url


@pytest.mark.django_db
def test_submit_comment(client, on_commit_immediately):
    blog = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="""
        ttest test
        """,
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    url = reverse("submit", args=[blog.oid])
    response = client.get(url)
    assert response.status_code == 405

    response = client.post(url, {})
    assert response.status_code == 400

    data = {
        "comment": "Hey there!\n\n",
        "name": " Peter ",
        "email": "test@peterbe.com ",
    }
    response = client.post(url, data)
    assert response.status_code == 200
    sent = mail.outbox[-1]
    assert sent.to[0] == settings.MANAGERS[0][1]

    blog_comment = BlogComment.objects.get(
        blogitem=blog,
        parent=None,
        approved=False,
        comment=data["comment"].strip(),
        name=data["name"].strip(),
        email=data["email"].strip(),
    )
    assert blog_comment.comment_rendered
    response = client.post(url, data)
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert BlogComment.objects.all().count() == 1


@pytest.mark.django_db
def test_submit_reply_comment(client, on_commit_immediately):
    blog = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="""
        ttest test
        """,
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    blog_comment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blog,
        approved=True,
        comment="Sure!",
        name="Greger",
        email="greger@example.com",
    )
    assert blog_comment.oid
    url = reverse("submit", args=[blog.oid])

    response = client.post(
        url,
        {
            "parent": blog_comment.oid,
            "comment": "Hey there!\n\n",
            "name": " Peter ",
            "email": "test@peterbe.com ",
        },
    )
    assert response.status_code == 200
    sent = mail.outbox[-1]
    assert sent.to[0] == settings.MANAGERS[0][1]

    assert BlogComment.objects.filter(parent=blog_comment)


@pytest.mark.django_db
def test_spam_prevention(client, settings):
    settings.SPAM_URL_PATTERNS = ["http*://www.spam.com"]

    blog = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="""
        ttest test
        """,
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    url = reverse("submit", args=[blog.oid])

    data = {"comment": "This is www.spam.com isn't it", "name": "", "email": ""}

    response = client.post(url, data)
    assert response.status_code == 400


@pytest.mark.django_db
def test_paginate_comment_capped(client, settings):
    settings.MAX_RECENT_COMMENTS = 10
    settings.MAX_BLOGCOMMENT_PAGES = 9  # as long as it's large
    blogitem = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="Test test",
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    bulk = []
    _range = settings.MAX_RECENT_COMMENTS * 3 + 1
    for i in range(_range):
        bulk.append(
            BlogComment(
                blogitem=blogitem,
                comment="Comment #{0:02}".format(i + 1),
                comment_rendered="Comment #{0:02}".format(i + 1),
                oid=BlogComment.next_oid(),
                approved=True,
                add_date=timezone.now() - datetime.timedelta(hours=_range - i),
            )
        )
    BlogComment.objects.bulk_create(bulk)
    cached_count = blogitem.count_comments(refresh=True)
    actual_count = BlogComment.objects.filter(blogitem=blogitem).count()
    assert cached_count == actual_count
    assert actual_count == 31

    url = reverse("blog_post", args=[blogitem.oid])
    response = client.get(url)
    assert response.status_code == 200
    assert "Comment #31" in response.content.decode("utf-8")
    assert "Comment #30" in response.content.decode("utf-8")
    assert "Comment #21" not in response.content.decode("utf-8")

    url_page_2 = reverse("blog_post", args=[blogitem.oid, 2])
    response = client.get(url_page_2)
    assert response.status_code == 200
    # Expect page 3 to be there
    url_page_3 = reverse("blog_post", args=[blogitem.oid, 3])
    assert url_page_3 in response.content.decode("utf-8")
    assert "Comment #21" in response.content.decode("utf-8")
    assert "Comment #20" in response.content.decode("utf-8")
    assert "Comment #11" not in response.content.decode("utf-8")

    response = client.get(url_page_3)
    assert response.status_code == 200
    # Expect page 4 to be there
    url_page_4 = reverse("blog_post", args=[blogitem.oid, 4])
    assert url_page_4 in response.content.decode("utf-8")
    assert "Comment #01" not in response.content.decode("utf-8")
    assert "Comment #02" in response.content.decode("utf-8")
    assert "Comment #03" in response.content.decode("utf-8")
    assert "Comment #12" not in response.content.decode("utf-8")

    response = client.get(url_page_4)
    assert response.status_code == 200
    assert "Comment #01" in response.content.decode("utf-8")
    assert "Comment #02" not in response.content.decode("utf-8")

    # Expect page 5 to NOT be there
    url_page_5 = reverse("blog_post", args=[blogitem.oid, 5])
    assert url_page_5 not in response.content.decode("utf-8")
    # Suppose you try to go there anyway!
    response = client.get(url_page_5)
    assert response.status_code == 404

    # Suppose it's capped!
    settings.MAX_BLOGCOMMENT_PAGES = 3
    response = client.get(url_page_3)
    assert response.status_code == 404
    # But, page 2 should still work
    response = client.get(url_page_2)
    assert response.status_code == 200
