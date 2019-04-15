import datetime
import os
from urllib.parse import urlparse

import pytest
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from peterbecom.plog.models import BlogItem, BlogComment, Category


@pytest.mark.django_db
def test_homepage_cache_rendering(client, tmpfscacheroot):
    url = reverse("home")

    blog1 = BlogItem.objects.create(
        title="TITLE1",
        text="BLABLABLA",
        display_format="structuredtext",
        pub_date=timezone.now() - datetime.timedelta(seconds=10),
    )
    BlogComment.objects.create(
        oid="c1", comment="textext", blogitem=blog1, approved=True
    )

    BlogComment.objects.create(
        oid="c2", comment="tuxtuxt", blogitem=blog1, approved=True
    )

    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "TITLE1" in content
    assert "2 comments" in content

    blog1.title = "TUTLE1"
    blog1.save()
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "TUTLE1" in content

    blog2 = BlogItem.objects.create(
        oid="t2",
        title="TATLE2",
        text="BLEBLE",
        display_format="structuredtext",
        pub_date=timezone.now() - datetime.timedelta(seconds=1),
    )

    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "TATLE2" in content
    assert "0 comments" in content
    assert "TUTLE1" in content
    assert "2 comments" in content

    # by categories only
    cat1 = Category.objects.create(name="CATEGORY1")
    cat2 = Category.objects.create(name="CATEGORY2")
    blog1.categories.add(cat1)
    blog1.save()
    blog2.categories.add(cat2)
    blog2.save()

    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "CATEGORY1" in content
    assert "CATEGORY2" in content

    url = reverse("only_category", args=["CATEGORY2"])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "CATEGORY1" not in content
    assert "CATEGORY2" in content

    url = reverse("only_category", args=["CATEGORY1"])
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "CATEGORY1" in content
    assert "CATEGORY2" not in content

    bulk = []
    for i in range(2, 21):
        bulk.append(
            BlogItem(
                oid="t-{}".format(i),
                title="TITLE-{}".format(i),
                text="BLEBLE",
                display_format="structuredtext",
                pub_date=timezone.now() - datetime.timedelta(seconds=20 + i),
            )
        )
    BlogItem.objects.bulk_create(bulk)

    url = reverse("home")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "/p2" in content
    visible_titles = []
    not_visible_titles = []
    for item in BlogItem.objects.all():
        if item.title in content:
            visible_titles.append(item.title)
        else:
            not_visible_titles.append(item.title)

    url = reverse("home_paged", args=(2,))
    response = client.get(url)
    content = response.content.decode("utf-8")
    batch_size = settings.HOMEPAGE_BATCH_SIZE
    for each in visible_titles[:batch_size]:
        assert each not in content
    for each in not_visible_titles[:batch_size]:
        assert each in content
    assert "/p3" in content


@pytest.mark.django_db
def test_about_page_fs_cached(client, tmpfscacheroot):
    fs_path = os.path.join(tmpfscacheroot, "about", "index.html")
    assert not os.path.isfile(fs_path)
    url = reverse("about")
    response = client.get(url)
    assert response.status_code == 200
    assert os.path.isfile(fs_path)


@pytest.mark.django_db
def test_about_page_with_newline_request_path(client, tmpfscacheroot):
    url = reverse("about")
    response = client.get(url + "\n")
    assert response.status_code == 301
    assert urlparse(response["location"]).path == url
