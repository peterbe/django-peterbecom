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
                if parsed.query:
                    query_params = parse_qs(parsed.query)
                    if search_engine == "Google":
                        search = query_params.get("q", [None])[0]
                    elif search_engine == "Yandex":
                        search = query_params.get("text", [None])[0]
                    else:
                        print(parsed)
                        print("Query parsed:", query_params)
                        raise NotImplementedError("TODO: Parse search query")
            else:
                print("MUST BE DIFFERENT SITE", referrer)
    else:
        direct = True

    if len(referrer) > 500:
        referrer = referrer[: 500 - 3] + "..."
    if pathname and len(pathname) > 300:
        pathname = pathname[: 300 - 3] + "..."
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
    for find in re.findall(
        r"\b(google|bing|yandex|yahoo|search\.brave|duckduckgo|ecosia)\.[a-z]{2,6}\b",
        netloc,
    ):
        if find == "search.brave":
            return "Brave"
        return find.capitalize()

    if "google" in netloc:
        # raise NotImplementedError(f"regex didn't work ({netloc!r})")
        print(f"regex didn't work ({netloc!r}) ??")


assert get_search_engine("www.google.com") == "Google"
assert get_search_engine("www.google.co.uk") == "Google"
assert get_search_engine("google.co.uk") == "Google"
assert get_search_engine("google.com") == "Google"
assert get_search_engine("search.brave.com") == "Brave"
