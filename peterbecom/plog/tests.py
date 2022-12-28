import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem, BlogItemHit


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

    (hit,) = BlogItemHit.objects.all()
    assert hit.blogitem == blog
