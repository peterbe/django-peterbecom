import datetime
import time

import pytest
import requests_mock
from django.utils import timezone

from peterbecom.base import tasks
from peterbecom.base.models import CDNPurgeURL


@pytest.mark.django_db
def test_run_purge_cdn_urls(monkeypatch, settings):
    monkeypatch.setattr(time, "sleep", lambda _: None)

    purge1 = CDNPurgeURL.objects.create(
        url="/foo/bar",
    )
    purge1.created = timezone.now() - datetime.timedelta(days=1)
    purge1.save()
    print("purge1.created", purge1.created)
    purge1.refresh_from_db()
    print("purge1.created", purge1.created)
    purge2 = CDNPurgeURL.objects.create(
        url="/foo/bar",
    )
    purge2.created = timezone.now() - datetime.timedelta(minutes=1)
    purge2.save()

    settings.SEND_KEYCDN_PURGES = True
    settings.KEYCDN_API_KEY = "secret"

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.keycdn.com/zones/129339.json",
            json={"data": {"zone": {"cachebr": "enabled"}}},
        )
        m.delete(
            "https://api.keycdn.com/zones/purgeurl/129339.json",
            json={"status": "success"},
        )

        tasks.run_purge_cdn_urls()

        assert not CDNPurgeURL.objects.filter(id=purge1.id).exists()
        assert CDNPurgeURL.objects.filter(id=purge2.id).exists()
        purge2.refresh_from_db()
