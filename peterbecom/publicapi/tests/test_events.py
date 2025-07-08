import json
import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

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


@pytest.mark.django_db
def test_post_duplicate_event(client):
    url = reverse("publicapi:events_event")
    uuid_ = generate_random_uuid()

    payload = {
        "type": "some-thing",
        "meta": {
            "uuid": uuid_,
            "sid": generate_random_uuid(),
            "url": "https://example.com",
            "created": timezone.now().isoformat(),
            "performance": {"nav": 123.4},
        },
        "data": {"pathname": "/value", "search": "foo"},
    }
    response = client.post(
        url,
        json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert AnalyticsEvent.objects.count() == 1

    payload["meta"]["created"] = (timezone.now() + timedelta(seconds=1)).isoformat()
    response = client.post(
        url,
        json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AnalyticsEvent.objects.count() == 1

    payload["meta"]["performance"]["nav"] = 987.1
    response = client.post(
        url,
        json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert AnalyticsEvent.objects.count() == 1

    payload["data"]["pathname"] = "/different"
    response = client.post(
        url,
        json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert AnalyticsEvent.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_agent, is_bot",
    [
        (
            "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)",
            True,
        ),
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36",
            True,
        ),
        ("Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", True),
        ("Site24x7", True),
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
            True,
        ),
        (
            "Mozilla/5.0 (Linux; Android 7.0;) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; PetalBot;+https://webmaster.petalsearch.com/site/petalbot)",
            True,
        ),
        (
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
            True,
        ),
        (
            "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)",
            True,
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
            True,
        ),
        ("Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)", True),
        # Some that are NOT bots
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
            False,
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.43",
            False,
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            False,
        ),
    ],
)
def test_post_event_bot_agent(client, user_agent, is_bot):
    url = reverse("publicapi:events_event")
    uuid_ = generate_random_uuid()
    response = client.post(
        url,
        json.dumps(
            {
                "type": "bot-test",
                "meta": {
                    "uuid": uuid_,
                    "url": "https://example.com",
                    "user_agent": {"ua": user_agent},
                },
                "data": {},
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201
    event = AnalyticsEvent.objects.get(
        uuid=uuid_, url="https://example.com", type="bot-test"
    )
    if is_bot:
        assert event.data["is_bot"]
        assert event.data["bot_agent"]
    else:
        assert not event.data["is_bot"]
        assert event.data["bot_agent"] is None
