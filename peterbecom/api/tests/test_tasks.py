import datetime

import pytest
from django.contrib.sites.models import Site
from django.core import mail
from django.utils import timezone

from peterbecom.api import tasks
from peterbecom.plog.models import BlogComment, BlogItem


@pytest.mark.django_db
def test_send_comment_reply_email_page_1():
    blogitem = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="Test test",
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    parent_comment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blogitem,
        name="Rooter",
        email="rooter@example.com",
        comment="This is the root comment",
        approved=True,
    )
    blogcomment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blogitem,
        comment="Ma reply!",
        approved=True,
        parent=parent_comment,
    )
    tasks.send_comment_reply_email(blogcomment.id)

    sent = mail.outbox[-1]
    assert "Reply to your comment" in sent.subject
    assert sent.to == ["rooter@example.com"]

    comment_absolute_url = "https://" + Site.objects.get_current().domain
    comment_absolute_url += f"/plog/{blogitem.oid}"
    comment_absolute_url += f"/comment/{parent_comment.oid}"
    assert comment_absolute_url in sent.body


@pytest.mark.django_db
def test_send_comment_reply_email_page_2(settings):
    settings.MAX_RECENT_COMMENTS = 10
    blogitem = BlogItem.objects.create(
        oid="myoid",
        title="TITLEX",
        text="Test test",
        display_format="markdown",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    bulk = []
    max_ = settings.MAX_RECENT_COMMENTS
    for i in range(max_):
        comment = "Comment number {}".format(i + 1)
        bulk.append(
            BlogComment(
                oid=BlogComment.next_oid(),
                blogitem=blogitem,
                name="Rooter",
                email="rooter@example.com",
                comment=comment,
                comment_rendered=comment,
                approved=True,
                add_date=timezone.now() - datetime.timedelta(seconds=1, hours=max_ - i),
            )
        )
    BlogComment.objects.bulk_create(bulk)

    parent_comment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blogitem,
        name="Rooter",
        email="rooter@example.com",
        comment="This is the root comment",
        approved=True,
        # Make it so old that it goes into page 2
        add_date=timezone.now() - datetime.timedelta(seconds=1, hours=max_ + 1),
    )
    middle_blogcomment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blogitem,
        comment="First reply!",
        email="middle@example.com",
        approved=True,
        parent=parent_comment,
    )
    blogcomment = BlogComment.objects.create(
        oid=BlogComment.next_oid(),
        blogitem=blogitem,
        comment="Deeper reply",
        approved=True,
        parent=middle_blogcomment,
    )
    tasks.send_comment_reply_email(blogcomment.id)

    sent = mail.outbox[-1]
    assert "Reply to your comment" in sent.subject
    assert sent.to == ["middle@example.com"]

    comment_absolute_url = "https://" + Site.objects.get_current().domain
    comment_absolute_url += f"/plog/{blogitem.oid}/p2"
    comment_absolute_url += "#" + middle_blogcomment.oid
    assert comment_absolute_url in sent.body
