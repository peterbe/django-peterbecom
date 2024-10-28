import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse

from peterbecom.base.models import AnalyticsEvent


def generate_random_uuid():
    return str(uuid.uuid4())


def json_datetime(obj):
    return DjangoJSONEncoder().default(obj)


def test_admin_required(client):
    url = reverse("api:analytics_query")
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    url = reverse("api:analytics_query")
    response = admin_client.get(
        url,
        {
            "query": """
                    SELECT count(*) FROM analytics where type = 'bla'
            """
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert not data["error"]
    assert data["meta"]["count_rows"] == 1
    assert not data["meta"]["maxed_rows"]
    assert data["meta"]["took_seconds"]
    assert data["rows"][0] == {"count": 0}


def test_bad_request(admin_client):
    url = reverse("api:analytics_query")
    response = admin_client.get(url)
    assert response.status_code == 400
    response = admin_client.get(url, {"query": ""})
    assert response.status_code == 400
    response = admin_client.get(url, {"query": "this is not a valid query"})
    assert response.status_code == 400
    response = admin_client.get(url, {"query": "delete from analytics"})
    assert response.status_code == 400
    response = admin_client.get(url, {"query": "select count(*) from plog_blogitem"})
    assert response.status_code == 400

    response = admin_client.get(
        url,
        {
            "query": """
                    SELECT count(*) FROM analytics where x = 'y'
            """
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]


def test_happy_path(admin_client):
    AnalyticsEvent.objects.create(
        type="pageview",
        uuid=generate_random_uuid(),
        url="https://www.peterbe.com/plog/abc123",
        meta={"user_agent": "Mozilla/5.0"},
        data={"foo": "bar"},
    )
    url = reverse("api:analytics_query")
    response = admin_client.get(
        url,
        {
            "query": """
                    SELECT created, data->'foo' as foo
                    FROM analytics where type = 'pageview'
            """
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert not data["error"]
    (first,) = data["rows"]
    assert first["created"]
    assert first["foo"]
