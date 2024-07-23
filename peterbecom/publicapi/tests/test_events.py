import json
import uuid

import pytest
from django.urls import reverse

from peterbecom.base.models import AnalyticsEvent


def generate_random_uuid():
    return str(uuid.uuid4())


@pytest.mark.django_db
def test_post_event_happy_path(client):
    url = reverse("publicapi:events_event")
    uuid_ = generate_random_uuid()
    response = client.post(
        url,
        json.dumps(
            {
                "type": "some-thing",
                "meta": {
                    "uuid": uuid_,
                    "url": "https://example.com",
                },
                "data": {
                    "key": "value",
                },
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201
    event = AnalyticsEvent.objects.get(
        uuid=uuid_, url="https://example.com", type="some-thing"
    )
    assert event.created
    assert event.data["key"] == "value"


@pytest.mark.django_db
def test_post_event_empty_default_data(client):
    url = reverse("publicapi:events_event")
    uuid_ = generate_random_uuid()
    response = client.post(
        url,
        json.dumps(
            {
                "type": "some-thing",
                "meta": {
                    "uuid": uuid_,
                    "url": "https://example.com",
                },
                "data": {},
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201
    event = AnalyticsEvent.objects.get(
        uuid=uuid_, url="https://example.com", type="some-thing"
    )
    assert event.created
    assert event.data == {}


@pytest.mark.django_db
def test_post_event_missing_keys(client):
    url = reverse("publicapi:events_event")
    response = client.post(url, json.dumps({}), content_type="application/json")
    assert response.status_code == 400

    response = client.post(
        url, json.dumps({"meta": {}}), content_type="application/json"
    )
    assert response.status_code == 400

    response = client.post(
        url,
        json.dumps(
            {
                "meta": {
                    "uuid": generate_random_uuid(),
                }
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    response = client.post(
        url,
        json.dumps(
            {
                "type": "",
                "meta": {
                    "uuid": generate_random_uuid(),
                    "url": "https://example.com",
                },
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_event_no_body(client):
    url = reverse("publicapi:events_event")
    response = client.post(url)
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_event_invalid_json(client):
    url = reverse("publicapi:events_event")
    response = client.post(url, "{{{}", content_type="application/json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_post_event_with_get(client):
    url = reverse("publicapi:events_event")
    response = client.get(url)
    assert response.status_code == 405
