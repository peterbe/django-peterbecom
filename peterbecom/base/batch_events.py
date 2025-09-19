import datetime
import json
import uuid
from typing import Any

from django.conf import settings
from django_redis import get_redis_connection

from peterbecom.base.models import bulk_create_events

LIST_KEY = "batch_events"

redis_client = get_redis_connection("default")


def log(*args: list[Any]):
    if not settings.RUNNING_TESTS:
        print("BATCH_EVENTS:", *args)


def create_event_later(type: str, uuid: str, url: str, meta: dict, data: dict):
    # Here you would implement the logic to create the event later
    redis_client.rpush(
        LIST_KEY,
        json.dumps(
            {"type": type, "uuid": uuid, "url": url, "meta": meta, "data": data},
            cls=DateTimeEncoder,
        ),
    )


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


def process_batch_events(batch_limit=100):
    count = redis_client.llen(LIST_KEY)
    log(f"In the queue, there are: {count}")
    if not count:
        log("No events in the queue. Exiting early.")
        return

    bulk = []
    while event_raw := redis_client.lpop(LIST_KEY):
        event = json.loads(event_raw)
        bulk.append(event)
        if len(bulk) >= batch_limit:
            log(f"Sending {len(bulk)} events in bulk...")
            bulk_create_events(bulk)
            bulk = []

    if bulk:
        log(f"Sending {len(bulk)} events in bulk...")
        bulk_create_events(bulk)

    count = redis_client.llen(LIST_KEY)
