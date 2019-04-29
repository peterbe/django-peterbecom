import datetime
import random
import math

from requests.exceptions import ReadTimeout, ConnectTimeout

from django import http
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Sum, Min, Max
from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.contrib.sites.requests import RequestSite
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.conf import settings

from peterbecom.podcasttime.models import Podcast, Episode, Picked
from peterbecom.podcasttime.search import PodcastDoc
from peterbecom.podcasttime.forms import PodcastsForm
from peterbecom.podcasttime.utils import is_html_document
from peterbecom.podcasttime.scraper import itunes_search
from peterbecom.podcasttime.tasks import (
    download_episodes_task,
    redownload_podcast_image,
    fetch_itunes_lookup,
    download_podcast_metadata,
    search_by_itunes,
)


def random_string(length):
    pool = list("abcdefghijklmnopqrstuvwxyz")
    pool.extend([x.upper() for x in pool])
    pool.extend("0123456789")
    random.shuffle(pool)
    return "".join(pool[:length])


def make_absolute_url(uri, request):
    prefix = request.is_secure() and "https" or "http"
    if uri.startswith("//"):
        # we only need the prefix
        return "%s:%s" % (prefix, uri)
    else:
        return "%s://%s%s" % (prefix, RequestSite(request).domain, uri)


def index(request):
    return redirect("https://podcasttime.io", permanent=True)


def find(request):
    if not (request.GET.get("ids") or request.GET.get("q")):
        return http.HttpResponseBadRequest("no ids or q")

    found = []
    max_ = 5
    q = None
    total = None

    cutoff = timezone.now() - datetime.timedelta(
        days=settings.LATEST_PODCAST_CUTOFF_DAYS
    )

    def package_podcast(podcast):
        if type(podcast) is Podcast:
            return podcast.to_search_doc()
        else:
            # remove summary fields since it's rather large
            podcast.pop("summary", None)

            if "episodes_count" not in podcast:
                # better than undefined
                podcast["episodes_count"] = None
            podcast["total_hours"] = None
            if podcast.get("episodes_seconds"):
                podcast["total_hours"] = podcast.pop("episodes_seconds") / 3600

            try:
                if podcast["latest_episode"] < cutoff:
                    podcast["_outdated"] = True
                else:
                    podcast["_outdated"] = False
            except KeyError:
                podcast["_outdated"] = True
            return podcast

    if request.GET.get("ids"):
        search = PodcastDoc.search()
        ids = [int(x) for x in request.GET["ids"].split(",")]
        search = search.filter("terms", id=ids)
        response = search.execute()
        if not response.hits.total:
            podcasts_orm = Podcast.objects.filter(id__in=ids)
            for podcast in podcasts_orm.filter(error__isnull=True):
                if not podcast.total_seconds or not podcast.last_fetch:
                    cache_key = "resubmit:{}".format(podcast.id)
                    if not cache.get(cache_key):
                        print(
                            "Forcing {!r} (id={}) to download episodes".format(
                                podcast.name, podcast.id
                            )
                        )
                        download_episodes_task(podcast.id)
                        cache.set(cache_key, True, 60)
                else:
                    podcast.save()
        for hit in response.hits:
            podcast = package_podcast(hit.to_dict())
            if (
                podcast["episodes_count"] is None
                or not podcast.get("last_fetch")
                or podcast["last_fetch"] < (timezone.now() - datetime.timedelta(days=7))
            ):
                cache_key = "resubmit:{}".format(podcast["id"])
                if not cache.get(cache_key):
                    print(
                        "Forcing {!r} (id={}) to download episodes".format(
                            podcast["name"], podcast["id"]
                        )
                    )
                    download_episodes_task(podcast["id"])
                    cache.set(cache_key, True, 60)
                podcast["_updating"] = True
            found.append(podcast)
        # rearrange them in the order they were
        found = sorted(found, key=lambda x: ids.index(x["id"]))

    elif request.GET.get("submitted"):
        q = request.GET["q"]
        try:
            results = itunes_search(q, attribute="titleTerm", timeout=6)["results"]
        except (ReadTimeout, ConnectTimeout):
            results = []

        for result in results[:max_]:
            if not result.get("feedUrl"):
                print("Weird result", result)
                continue
            try:
                podcast = Podcast.objects.get(
                    url=result["feedUrl"], name=result["collectionName"]
                )
            except Podcast.DoesNotExist:
                assert result["collectionName"], result
                podcast = Podcast.objects.create(
                    name=result["collectionName"],
                    url=result["feedUrl"],
                    itunes_lookup=result,
                    image_url=result["artworkUrl600"],
                )
                try:
                    podcast.download_image(timeout=3)
                except (ReadTimeout, ConnectTimeout):
                    redownload_podcast_image(podcast.id)
                download_episodes_task(podcast.id)
                # Reload since the task functions operate on a new instance
                # podcast = Podcast.objects.get(id=podcast.id)
            found.append(package_podcast(podcast))
    else:
        q = request.GET["q"]
        search = PodcastDoc.search()
        search = search.query("match_phrase", name=q)
        search = search[:max_]
        response = search.execute()
        total = response.hits.total
        for hit in response.hits:
            podcast = package_podcast(hit.to_dict())
            if podcast["episodes_count"] is None:
                cache_key = "resubmit:{}".format(podcast["id"])
                if not cache.get(cache_key):
                    print(
                        "Forcing {!r} (id={}) to download episodes".format(
                            podcast["name"], podcast["id"]
                        )
                    )
                    download_episodes_task(podcast["id"])
                    cache.set(cache_key, True, 60)
                    # this will force the client-side to re-query for this
                    podcast["last_fetch"] = None
            found.append(podcast)
        if total < 5:
            print("NOTHING FOUND!", q, "SENDING IT TO iTUNES")
            search_by_itunes(q)

    if total is None:
        total = len(found)
    return http.JsonResponse({"items": found, "total": total, "q": q})


@csrf_exempt
@transaction.atomic
@require_POST
def picked(request):
    form = PodcastsForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)
    if request.POST.get("picks"):
        picked_obj = Picked.objects.get(session_key=request.POST["picks"])
    else:
        picked_obj = None
    podcasts = Podcast.objects.filter(id__in=form.cleaned_data["ids"])
    if picked_obj:
        # append
        picked_obj.podcasts.clear()
    else:
        # create with first pick
        session_key = random_string(32)
        picked_obj = Picked.objects.create(session_key=session_key)
    picked_obj.podcasts.add(*podcasts)
    return http.JsonResponse({"session_key": picked_obj.session_key})


def stats(request):
    form = PodcastsForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    cutoff = timezone.now() - datetime.timedelta(
        days=settings.LATEST_PODCAST_CUTOFF_DAYS
    )

    for podcast in Podcast.objects.filter(id__in=form.cleaned_data["ids"]):
        first_published = Episode.objects.filter(podcast=podcast).aggregate(
            first=Min("published")
        )["first"]
        if first_published:
            cutoff = max(cutoff, first_published)

    episodes = Episode.objects.filter(
        podcast_id__in=form.cleaned_data["ids"], published__gte=cutoff
    )

    episodes = episodes.values("podcast_id").annotate(
        duration=Sum("duration"), min=Min("published"), max=Max("published")
    )
    total_duration_days = 0.0
    min_dates = []
    max_dates = []
    for each in episodes:
        total_duration_days += each["duration"]
        min_dates.append(each["min"])
        max_dates.append(each["max"])

    if total_duration_days > 0 and min_dates != max_dates:
        max_date = max(max_dates)
        min_date = min(min_dates)
        days = (max_date - min_date).days
        # minutes per day
        per_day = total_duration_days / days / 3600
        numbers = {
            "per_day": per_day,
            "per_week": per_day * 7,
            "per_month": per_day * (365 / 12.0),
            "max_date": max_date,
            "min_date": min_date,
        }
    else:
        numbers = {"per_day": 0, "per_week": 0, "per_month": 0}
    return http.JsonResponse(numbers)


def stats_episodes(request):
    form = PodcastsForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    # episodes = Episode.objects.filter(
    #     podcast_id__in=form.cleaned_data['ids'],
    # )
    #
    # episodes = episodes.values(
    #     'podcast_id',
    # ).annotate(
    #     duration=Sum('duration'),
    #     min=Min('published'),
    #     max=Max('published'),
    # )
    # rates = []
    # for each in episodes:
    #     days = (each['max'] - each['min']).days
    #     if days:
    #         rates.append(
    #             # hours per day
    #             1.0 * each['duration'] / days / 3600
    #         )
    #
    # if rates:
    #     average = sum(rates) / len(rates)
    # else:
    #     average = 0.0
    # numbers = {
    #     'per_day': average,
    #     'per_week': average * 7,
    #     'per_month': average * (365 / 12.0),
    # }

    cutoff = timezone.now() - datetime.timedelta(
        days=settings.LATEST_PODCAST_CUTOFF_DAYS
    )

    episodes_ = []
    for podcast in Podcast.objects.filter(id__in=form.cleaned_data["ids"]):
        episodes_qs = Episode.objects.filter(
            podcast=podcast, published__gte=cutoff, duration__gt=0
        ).only("published", "duration")
        items = []
        for episode in episodes_qs.order_by("published"):
            items.append({"date": episode.published, "duration": episode.duration})
        episodes_.append({"name": podcast.name, "episodes": items})

    return http.JsonResponse({"episodes": episodes_})


def legacy_podcasts(request):
    return redirect("https://podcasttime.io", permanent=True)


@cache_page(settings.DEBUG and 10 or 60 * 60)
def podcasts_data(request):
    context = {}
    search_term = request.GET.get("search", "").strip()

    search = PodcastDoc.search()
    if search_term:
        search = search.query("match_phrase", name=search_term)

    search = search.sort("-times_picked", "_score")
    page = request.GET.get("page", 1)
    page_index = int(page) - 1
    assert page_index >= 0, page_index
    batch_size = 15
    if page_index > 0:
        # need to check that it's not out of bounds
        response = PodcastDoc.search().execute()
        if batch_size * (1 + page_index) > response.hits.total:
            raise http.Http404("Page too big")
    search = search[page_index * batch_size : (page_index + 1) * batch_size]

    response = search.execute()
    context["count"] = response.hits.total

    items = []
    for hit in response.hits:
        items.append(hit.to_dict())

    context["items"] = items

    pagination = {
        "has_previous": page_index > 0,
        "has_next": (page_index + 1) * batch_size < context["count"],
        "number": page_index + 1,
        "num_pages": math.ceil(context["count"] / batch_size),
    }
    if pagination["has_previous"]:
        pagination["previous_page_number"] = page_index
    if pagination["has_next"]:
        pagination["next_page_number"] = page_index + 2
    context["pagination"] = pagination
    return http.JsonResponse(context)


@cache_page(settings.DEBUG and 10 or 60 * 60)
def podcasts_table(request):
    context = {}
    page_size = int(request.GET.get("page_size", 10))
    page = int(request.GET.get("page", 0))
    sorting = request.GET.getlist("sorting")

    qs = Podcast.objects.all()
    order_by = []
    if not sorting:
        order_by.append("-modified")
    else:
        for key, desc in [x.split(":", 1) for x in sorting]:
            if desc == "false":
                key = "-{}".format(key)
            order_by.append(key)
    qs = qs.order_by(*order_by)
    paginator = Paginator(qs, page_size)
    paged = paginator.page(page + 1)

    rows = []
    for podcast in paged:
        rows.append(
            {
                "id": podcast.id,
                "name": podcast.name,
                "last_fetch": podcast.last_fetch,
                "error": podcast.error,
                "times_picked": podcast.times_picked,
                "latest_episode": podcast.latest_episode,
                "slug": podcast.get_or_create_slug(),
                "created": podcast.created,
                "modified": podcast.modified,
                "episodes_count": Episode.objects.filter(podcast=podcast).count(),
            }
        )
    context["rows"] = rows
    context["pages"] = paginator.num_pages
    return http.JsonResponse(context)


def podcast_episodes(request, id):
    podcast = get_object_or_404(Podcast, id=id)
    context = {}
    episodes = Episode.objects.filter(podcast=podcast)

    if (
        not episodes.exists()
        or episodes.count() == episodes.filter(title__isnull=True).count()
    ):
        download_episodes_task(id)

    if podcast.link is None and podcast.summary is None and podcast.subtitle is None:
        cache_key = "download_podcast_metadata:{}".format(podcast.id)
        if not cache.get(cache_key):
            download_podcast_metadata(podcast.id)
            cache.set(cache_key, True, 60)

    context["episodes"] = []
    for episode in episodes.order_by("-published"):
        context["episodes"].append(
            {
                "duration": episode.duration,
                "published": episode.published,
                "title": episode.title,
                "summary": episode.summary,
                "guid": episode.guid,
            }
        )
    return http.JsonResponse(context)


def legacy_picks(request):
    return redirect("https://podcasttime.io/picks", permanent=True)


@cache_page(settings.DEBUG and 10 or 60)
def picks_data(request):
    context = {}
    qs = Picked.objects.all().order_by("-modified")
    paginator = Paginator(qs, 15)
    page = request.GET.get("page")
    try:
        paged = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        paged = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        paged = paginator.page(paginator.num_pages)

    items = []

    # First build up a map that maps all unique podcast IDs to
    # a little dict.
    # Then when doing the nested loop, later, we have already done
    # this work for each *unique* podcast only once.
    all_podcasts = {}
    for pick in paged:
        for podcast in pick.podcasts.all():
            if podcast.id not in all_podcasts:
                all_podcasts[podcast.id] = {
                    "name": podcast.name,
                    "image": (
                        podcast.image and podcast.get_thumbnail_url("348x348") or None
                    ),
                    "times_picked": podcast.times_picked,
                    "id": podcast.id,
                    "slug": podcast.get_or_create_slug(),
                }
    for pick in paged:
        podcasts = []
        for each in pick.podcasts.all().values("id"):
            podcasts.append(all_podcasts[each["id"]])
        items.append({"podcasts": podcasts, "id": pick.id})
    context["items"] = items

    pagination = {
        "has_previous": paged.has_previous(),
        "has_next": paged.has_next(),
        "number": paged.number,
        "num_pages": paginator.num_pages,
    }
    if pagination["has_previous"]:
        pagination["previous_page_number"] = paged.previous_page_number()
    if pagination["has_next"]:
        pagination["next_page_number"] = paged.next_page_number()
    context["pagination"] = pagination

    return http.JsonResponse(context)


def podcast(request, id, slug=None):
    podcast = get_object_or_404(Podcast, id=id)
    return redirect(
        "https://podcasttime.io/podcasts/{}/{}".format(podcast.id, podcast.slug),
        permanent=True,
    )


def podcast_data(request, id, slug=None):
    podcast = get_object_or_404(Podcast, id=id, slug__iexact=slug)
    context = {}
    context.update(
        {
            "id": podcast.id,
            "slug": podcast.slug,
            "name": podcast.name,
            "url": podcast.url,
            "image_url": podcast.image_url,
            "times_picked": podcast.times_picked,
            "total_seconds": podcast.total_seconds,
            "last_fetch": podcast.last_fetch,
            "latest_episode": podcast.latest_episode,
            "modified": podcast.modified,
        }
    )
    if podcast.error:
        context["_has_error"] = True
    if not podcast.last_fetch or podcast.last_fetch < timezone.now() - datetime.timedelta(
        days=7
    ):
        cache_key = "updating:episodes:{}".format(podcast.id)
        if not cache.get(cache_key):
            cache.set(cache_key, True, 60)
            download_episodes_task(podcast.id)
            context["_updating"] = True
    episodes = Episode.objects.filter(podcast=podcast).order_by("-published")
    if podcast.image and is_html_document(podcast.image.path):
        print("Found a podcast.image that wasn't an image")
        podcast.image = None
        podcast.save()
        redownload_podcast_image(podcast.id)
    elif not podcast.image and podcast.image_url:
        redownload_podcast_image(podcast.id)

    if podcast.itunes_lookup is None:
        fetch_itunes_lookup(podcast.id)

    if not episodes.exists():
        download_episodes_task(podcast.id)
    context["episodes_count"] = episodes.count()
    context["episodes"] = []
    for episode in episodes:
        context["episodes"].append(
            {
                "duration": episode.duration,
                "published": episode.published,
                "guid": episode.guid,
            }
        )
    try:
        thumb = podcast.get_thumbnail("348x348")
        context["thumb"] = {
            "url": thumb.url,
            "width": thumb.width,  # XXX is this ever used?!
            "height": thumb.height,
        }
    except IOError:
        # image is so busted it can't be turned into a thumbnail
        podcast.image = None
        podcast.save()
        context["thumb"] = None
        redownload_podcast_image(podcast.id)
    return http.JsonResponse(context)


@cache_page(60 * 60)
def general_stats(request, what):
    context = {}
    if what == "numbers":
        numbers = {}
        numbers["podcasts"] = Podcast.objects.all().count()
        numbers["picks"] = Picked.objects.all().count()
        numbers["episodes"] = Episode.objects.all().count()
        numbers["total_hours"] = int(
            Episode.objects.all().aggregate(count=Sum("duration"))["count"] / 3600
        )
        context["numbers"] = numbers
    else:
        raise NotImplementedError(what)
    return http.JsonResponse(context)
