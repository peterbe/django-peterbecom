import re
from functools import lru_cache
from urllib.parse import urlparse

from django.db.models import Max

from peterbecom.base.models import AnalyticsEvent
from peterbecom.plog.models import BlogItem, BlogItemHit


def analytics_to_blogitem_hits_backfill():
    last = BlogItemHit.objects.aggregate(max=Max("add_date"))["max"]
    events = AnalyticsEvent.objects.filter(created__gt=last, type="pageview").order_by(
        "created"
    )
    print(f"Last BlogItemHit add_date {last}. {events.count()} new events to process")
    page_regex = re.compile(r"(/p(\d+))$")
    batch = []
    for event in events:
        url_parsed = urlparse(event.url)
        path = url_parsed.path
        if not path.startswith("/plog/"):
            continue
        if path.startswith("/plog/blogitem-040601-1/song/") or path.startswith(
            "/plog/blogitem-040601-1/q/"
        ):
            continue
        page = None
        for _, number in page_regex.findall(path):
            try:
                page = int(number)
                path = page_regex.sub("", path)
            except ValueError:
                continue
        split = path.split("/")
        if len(split) != 3 or split[0] or split[1] != "plog":
            continue

        oid = split[2]
        blogitem = find_blogitem(oid)
        if not blogitem:
            print(f"WARNING: Invalid oid {oid!r}")
            continue

        http_referer = event.meta.get("referrer") or None
        if http_referer and len(http_referer) > 450:
            print(
                f"WARNING http_referer too long ({len(http_referer)}) {http_referer!r}"
            )
            http_referer = http_referer[:450]

        ip_address = event.meta.get("ip_address")
        if ip_address:
            ip_address = ip_address.split(",")[0]
        batch.append(
            BlogItemHit(
                blogitem=blogitem,
                add_date=event.created,
                remote_addr=ip_address,
                http_referer=http_referer,
                page=page,
            )
        )

    if batch:
        BlogItemHit.objects.bulk_create(batch)
        print(f"{len(batch)} new BlogItemHit objects created")
    else:
        print("No new BlogItemHit objects created")


@lru_cache
def find_blogitem(oid):
    try:
        return BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        pass
