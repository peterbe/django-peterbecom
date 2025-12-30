import pytest
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category, SearchDoc


@pytest.mark.django_db
def test_blogitem_to_search_doc():
    blogitem = BlogItem.objects.create(
        title="My first blog post",
        text="This is the **text** of my first blog post.",
        pub_date=timezone.now(),
    )
    search_doc = SearchDoc.objects.get(oid=blogitem.oid)
    assert search_doc.title == "My first blog post"
    blogitem.categories.add(Category.objects.create(name="Category1"))

    blogitem.proper_keywords = ["first", "blog", "post"]
    blogitem.save()
    search_doc.refresh_from_db()
    assert set(search_doc.keywords) == {"first", "blog", "post"}

    blogitem.delete()

    assert not SearchDoc.objects.filter(oid=blogitem.oid).exists()
