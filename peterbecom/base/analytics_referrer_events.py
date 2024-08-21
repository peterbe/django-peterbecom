import re
from urllib.parse import parse_qs, urlparse

from peterbecom.base.models import AnalyticsEvent, AnalyticsReferrerEvent


def create_analytics_referrer_events(max=100):
    qs = (
        AnalyticsEvent.objects.exclude(
            id__in=AnalyticsReferrerEvent.objects.values_list("event_id", flat=True)
        )
        .filter(type="pageview")
        .filter(meta__referrer__isnull=False)
        .order_by("-created")
    )

    batch = []
    for event in qs[:max]:
        referrer = event.meta["referrer"]
        referrer_event = referrer_to_referrer_event(event, referrer)
        batch.append(referrer_event)

    if batch:
        AnalyticsReferrerEvent.objects.bulk_create(batch)
        print(f"Created {len(batch)} new AnalyticsReferrerEvent instances")
    else:
        print("No new analytics referrer events created")


def referrer_to_referrer_event(event, referrer):
    search_engine = None
    search = None
    pathname = None

    if referrer:
        direct = False
        parsed = urlparse(referrer)
        event_url_parsed = urlparse(event.url)
        if parsed.netloc == event_url_parsed.netloc:
            pathname = parsed.path
            if pathname == "/search" and parsed.query:
                query_params = parse_qs(parsed.query)
                search = query_params.get("q", [None])[0]
        else:
            search_engine = get_search_engine(parsed.netloc)
            if search_engine:
                print(parsed)
                raise NotImplementedError("TODO: Parse search query")
            else:
                print("MUST BE DIFFERENT SITE", referrer)
    else:
        direct = True

    # print(
    #     dict(
    #         event=event,
    #         referrer=referrer,
    #         pathname=pathname,
    #         search_engine=search_engine,
    #         search=search,
    #         direct=direct,
    #     )
    # )
    return AnalyticsReferrerEvent(
        event=event,
        referrer=referrer,
        pathname=pathname,
        search_engine=search_engine,
        search=search,
        direct=direct,
        created=event.created,
    )


def is_google(netloc):
    return re.search(r"\bgoogle\.[a-z]{2,6}\b", netloc, re.IGNORECASE) is not None


def get_search_engine(netloc):
    for find in re.findall(r"\b(google|bing|yandex|yahoo)\.[a-z]{2,6}\b", netloc):
        return find.capitalize()
