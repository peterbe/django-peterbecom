import datetime
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone

from peterbecom.base.models import AnalyticsEvent
from peterbecom.llmcalls.models import LLMCall


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
                    SELECT data->'foo', created, data->'nonexist',
                      now() - created as delta
                    FROM analytics where type = 'pageview'
            """
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert not data["error"]
    (first,) = data["rows"]
    assert first["?column?"]
    assert first["?column? (2)"] is None
    assert first["delta"]
    assert first["created"]


def test_analytics_llmcalls(admin_client):
    url = reverse("api:analytics_llmcalls")
    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["aggregates"] == []
    assert data["sums"] == []

    LLMCall.objects.create(
        status="success",
        messages=[{"role": "user", "content": "Hello"}],
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-turbo",
        took_seconds=1.23,
        created=timezone.now() - datetime.timedelta(days=30),
    )
    LLMCall.objects.create(
        status="success",
        messages=[{"role": "user", "content": "Hello"}],
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-nano",
        took_seconds=15.6,
        created=timezone.now() - datetime.timedelta(days=30),
    )
    LLMCall.objects.create(
        status="success",
        messages=[{"role": "user", "content": "Hello"}],
        response={},
        model="gpt-3.5-nano",
        took_seconds=5.4,
    )

    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert len(data["aggregates"]) == 2  # 2 different months
    assert [x["count"] for x in data["aggregates"]] == [2, 1]

    assert len(data["sums"]) == 2  # 2 different models
    assert [x["count"] for x in data["sums"]] == [2, 1]
