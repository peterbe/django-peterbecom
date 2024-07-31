from django.core.cache import cache

from peterbecom.base.geo import ip_to_city
from peterbecom.base.models import AnalyticsEvent, AnalyticsGeoEvent


def create_analytics_geo_events(max=100):
    qs = (
        AnalyticsEvent.objects.exclude(
            id__in=AnalyticsGeoEvent.objects.values_list("event_id", flat=True)
        )
        .filter(type="pageview")
        .filter(meta__ip_address__isnull=False)
        .exclude(meta__ip_address="127.0.0.1")
        .order_by("-created")
    )

    batch = []
    for event in qs[:max]:
        cache_key = f"geo_event_failed_{event.id}"
        ip_address = event.meta["ip_address"]
        if cache.get(cache_key):
            print(f"{ip_address} already prior failed")
            continue
        geo_event = ip_address_to_geo_event(event, ip_address)
        if not geo_event:
            cache.set(cache_key, True, 60 * 60)
            continue

        batch.append(geo_event)
    if batch:
        AnalyticsGeoEvent.objects.bulk_create(batch)
        print(f"Created {len(batch)} new AnalyticsGeoEvent instances")
    else:
        print("No new analytics geo events created")


def ip_address_to_geo_event(event, ip_address):
    lookup = ip_to_city(ip_address)
    if not lookup:
        print(f"Lookup from {ip_address!r} failed")
        return

    country_code = lookup.get("country_code")
    region = lookup.get("region")
    city = lookup.get("city")
    country_name = lookup.get("country_name")
    if not country_code and not region and not city and not country_name:
        print("WARNING. Found but not found")
        print(lookup)
        return

    return AnalyticsGeoEvent(
        event=event,
        ip_address=ip_address,
        country_code=country_code,
        region=region,
        city=city,
        country=country_name,
        lookup=lookup,
        latitude=lookup.get("latitude"),
        longitude=lookup.get("longitude"),
    )
