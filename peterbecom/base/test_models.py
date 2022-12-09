import pytest

from peterbecom.base import models


@pytest.mark.django_db
def test_cdnpurgeurl_basics():

    models.CDNPurgeURL.add("/uri1")
    assert models.CDNPurgeURL.get() == ["/uri1"]
    models.CDNPurgeURL.add("/uri2")
    assert models.CDNPurgeURL.get() == ["/uri1", "/uri2"]
    models.CDNPurgeURL.add("/uri2")  # again!
    assert models.CDNPurgeURL.get() == ["/uri1", "/uri2"]  # uri2 is still last
    assert models.CDNPurgeURL.objects.filter(cancelled__isnull=False).count() == 1

    models.CDNPurgeURL.add("/uri1")  # should move it last
    assert models.CDNPurgeURL.get() == ["/uri2", "/uri1"]

    models.CDNPurgeURL.succeeded("/uri2")
    assert models.CDNPurgeURL.get() == ["/uri1"]

    try:
        1 / 0
    except Exception:
        models.CDNPurgeURL.failed("/uri1")

    (failed,) = models.CDNPurgeURL.objects.filter(exception__isnull=False)
    assert "ZeroDivisionError" in failed.exception

    assert models.CDNPurgeURL.get() == ["/uri1"]  # still there!
