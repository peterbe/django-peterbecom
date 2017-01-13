import datetime
import random

from requests.exceptions import ReadTimeout, ConnectTimeout

from django import http
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Sum, Min, Max, Count, Q
from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# from django.core.urlresolvers import reverse
from django.db import transaction
from django.contrib.sites.requests import RequestSite
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page

from peterbecom.podcasttime.models import Podcast, Episode, Picked
from peterbecom.podcasttime.forms import (
    CalendarDataForm,
    PodcastsForm,
)
from peterbecom.podcasttime.utils import is_html_document
from peterbecom.podcasttime.scraper import (
    itunes_search,
)
from peterbecom.podcasttime.tasks import (
    download_episodes_task,
    redownload_podcast_image,
    fetch_itunes_lookup,
)


def random_string(length):
    pool = list('abcdefghijklmnopqrstuvwxyz')
    pool.extend([x.upper() for x in pool])
    pool.extend('0123456789')
    random.shuffle(pool)
    return ''.join(pool[:length])


def make_absolute_url(uri, request):
    prefix = request.is_secure() and 'https' or 'http'
    if uri.startswith('//'):
        # we only need the prefix
        return '%s:%s' % (prefix, uri)
    else:
        return '%s://%s%s' % (
            prefix,
            RequestSite(request).domain,
            uri
        )


def index(request):
    return redirect('https://podcasttime.io', permanent=True)


def find(request):
    if not (request.GET.get('ids') or request.GET.get('q')):
        return http.HttpResponseBadRequest('no ids or q')

    found = []
    max_ = 5
    q = None

    if request.GET.get('ids'):
        ids = [int(x) for x in request.GET['ids'].split(',')]
        found = Podcast.objects.filter(id__in=ids)
        # rearrange them in the order they were
        found = sorted(found, key=lambda x: ids.index(x.id))
        # for podcast in found:
        #     if not podcast.last_fetch:
        #         download_episodes_task.delay(podcast.id)
    elif request.GET.get('itunes'):
        q = request.GET['q']
        try:
            results = itunes_search(
                q,
                attribute='titleTerm',
                timeout=6,
            )['results']
        except (ReadTimeout, ConnectTimeout):
            results = []

        for result in results:
            # pod = {
            #     'image_url': result['artworkUrl600'],
            #     'itunes_url': result['collectionViewUrl'],
            #     'artist_name': result['artistName'],
            #     'tags': result['genres'],
            #     'name': result['collectionName'],
            #     # 'feed_url': result['feedUrl'],
            # }
            try:
                podcast = Podcast.objects.get(
                    url=result['feedUrl'],
                    name=result['collectionName']
                )
            except Podcast.DoesNotExist:
                podcast = Podcast.objects.create(
                    name=result['collectionName'],
                    url=result['feedUrl'],
                    itunes_lookup=result,
                    image_url=result['artworkUrl600'],
                )
                try:
                    podcast.download_image(timeout=3)
                except (ReadTimeout, ConnectTimeout):
                    redownload_podcast_image(podcast.id)
                download_episodes_task.delay(podcast.id)
                # Reload since the task functions operate on a new instance
                # podcast = Podcast.objects.get(id=podcast.id)
            found.append(podcast)
    else:
        q = request.GET['q']
        items = []

        # import time
        # time.sleep(random.randint(1,4))
        base_qs = Podcast.objects.filter(error__isnull=True)
        podcasts = base_qs.filter(name__istartswith=q)
        for podcast in podcasts[:max_]:
            found.append(podcast)
        if len(q) > 2:
            sql = (
                "to_tsvector('english', name) @@ "
                "plainto_tsquery('english', %s)"
            )
            podcasts = base_qs.exclude(
                id__in=[x.id for x in found]
            ).extra(
                where=[sql],
                params=[q]
            )[:max_]
            for podcast in podcasts[:max_]:
                if len(found) >= max_:
                    break
                found.append(podcast)
        if len(q) > 1:
            podcasts = base_qs.filter(name__icontains=q).exclude(
                id__in=[x.id for x in found]
            )
            for podcast in podcasts[:max_]:
                if len(found) >= max_:
                    break
                found.append(podcast)

    def episodes_meta(podcast):
        episodes_cache_key = 'episodes-meta%s' % podcast.id
        meta = cache.get(episodes_cache_key)
        if meta is None:
            episodes = Episode.objects.filter(podcast=podcast)
            episodes_count = episodes.count()
            total_hours = None
            if episodes_count:
                total_seconds = episodes.aggregate(
                    duration=Sum('duration')
                )['duration']
                if total_seconds:
                    total_hours = total_seconds / 3600.0
            else:
                download_episodes_task.delay(podcast.id)
            meta = {
                'count': episodes_count,
                'total_hours': total_hours,
            }
            if episodes_count:
                cache.set(episodes_cache_key, meta, 60 * 60 * 24)
        return meta

    items = []
    for podcast in found:
        if podcast.image and is_html_document(podcast.image.path):
            print("Found a podcast.image that wasn't an image")
            podcast.image = None
            podcast.save()
        if podcast.image:
            if podcast.image.size < 1000:
                print("IMAGE LOOKS SUSPICIOUS")
                print(podcast.image_url)
                print(repr(podcast), podcast.id)
                print(podcast.url)
                print(repr(podcast.image.read()))
                podcast.download_image()
        thumb_url = None
        if podcast.image:
            try:
                thumb_url = podcast.get_thumbnail_url(
                    '160x160',
                    quality=81,
                    upscale=False
                )
                thumb_url = make_absolute_url(thumb_url, request)
            except IOError:
                import sys
                print("BAD IMAGE!")
                print(sys.exc_info())
                print(repr(podcast.image))
                print(repr(podcast), podcast.url)
                print()
                podcast.image = None
                podcast.save()
                redownload_podcast_image.delay(podcast.id)
        else:
            redownload_podcast_image.delay(podcast.id)

        # Temporarily put here
        if podcast.itunes_lookup is None:
            fetch_itunes_lookup.delay(podcast.id)

        meta = episodes_meta(podcast)
        episodes_count = meta['count']
        total_hours = meta['total_hours']
        items.append({
            'id': podcast.id,
            'name': podcast.name,
            'image_url': thumb_url,
            'episodes': episodes_count,
            'hours': total_hours,
            'last_fetch': podcast.last_fetch,
            'latest_episode': podcast.latest_episode,
            'slug': podcast.get_or_create_slug(),
            # 'url': reverse(
            #     'podcasttime:podcast_slug',
            #     args=(podcast.id, podcast.get_or_create_slug())
            # ),
        })
    return http.JsonResponse({
        'items': items,
        'q': q,
    })


@csrf_exempt
@transaction.atomic
@require_POST
def picked(request):
    form = PodcastsForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)
    if request.POST.get('picks'):
        picked_obj = Picked.objects.get(session_key=request.POST['picks'])
    else:
        picked_obj = None
    podcasts = Podcast.objects.filter(id__in=form.cleaned_data['ids'])
    if picked_obj:
        # append
        picked_obj.podcasts.clear()
    else:
        # create with first pick
        session_key = random_string(32)
        picked_obj = Picked.objects.create(
            session_key=session_key
        )
    picked_obj.podcasts.add(*podcasts)
    return http.JsonResponse({'session_key': picked_obj.session_key})


def calendar(request):
    form = CalendarDataForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    episodes = Episode.objects.filter(
        podcast__id__in=form.cleaned_data['ids'],
        published__gte=form.cleaned_data['start'],
        published__lt=form.cleaned_data['end'],
    ).select_related('podcast')
    colors = (
        "#EAA228", "#c5b47f", "#579575", "#839557", "#958c12",
        "#953579", "#4b5de4", "#d8b83f", "#ff5800", "#0085cc",
        "#c747a3", "#cddf54", "#FBD178", "#26B4E3", "#bd70c7",
    )
    next_color = iter(colors)
    items = []
    podcast_colors = {}
    for episode in episodes:
        duration = datetime.timedelta(seconds=episode.duration)
        if episode.podcast_id not in podcast_colors:
            podcast_colors[episode.podcast_id] = next_color.next()
        color = podcast_colors[episode.podcast_id]
        item = {
            'id': episode.id,
            'title': episode.podcast.name,
            'start': episode.published,
            'end': episode.published + duration,
            'color': color,
        }
        items.append(item)
    return http.JsonResponse(items, safe=False)


def stats(request):
    form = PodcastsForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)

    episodes = Episode.objects.filter(
        podcast_id__in=form.cleaned_data['ids'],
    )

    episodes = episodes.values(
        'podcast_id',
    ).annotate(
        duration=Sum('duration'),
        min=Min('published'),
        max=Max('published'),
    )
    rates = []
    for each in episodes:
        days = (each['max'] - each['min']).days
        if days:
            rates.append(
                # hours per day
                1.0 * each['duration'] / days / 3600
            )

    if rates:
        average = sum(rates) / len(rates)
    else:
        average = 0.0
    numbers = {
        'per_day': average,
        'per_week': average * 7,
        'per_month': average * (365 / 12.0),
    }
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
    episodes_ = []
    past = timezone.now() - datetime.timedelta(days=200)
    for podcast in Podcast.objects.filter(id__in=form.cleaned_data['ids']):
        episodes_qs = Episode.objects.filter(
            podcast=podcast,
            published__gte=past,
            duration__gt=0,
        ).only('published', 'duration')
        items = []
        for episode in episodes_qs.order_by('published'):
            items.append({
                'date': episode.published,
                'duration': episode.duration,
            })
        episodes_.append({
            'name': podcast.name,
            'episodes': items,
        })

    return http.JsonResponse({'episodes': episodes_})


def _search_podcasts(searchterm, podcasts=None):
    if podcasts is None:
        podcasts = Podcast.objects.all()

    directly = podcasts.filter(
        Q(url=searchterm) |
        Q(name=searchterm)
    )
    if directly.exists():
        return directly

    sql = (
        "to_tsvector('english', name) @@ "
        "plainto_tsquery('english', %s) "
        "OR name ILIKE %s"
    )
    podcasts = podcasts.extra(
        where=[sql],
        params=[
            searchterm,
            '%{}%'.format(searchterm),
        ]
    )

    return podcasts


def podcasts(request):
    return redirect('https://podcasttime.io', permanent=True)


def podcasts_data(request):
    context = {}
    search = request.GET.get('search', '').strip()
    ids = request.GET.get('ids')

    podcasts = Podcast.objects.exclude(name='')
    if search:
        podcasts = _search_podcasts(search, podcasts)

    if ids:
        ids = [int(x) for x in ids.split(',') if x.strip()]
        podcasts = podcasts.filter(id__in=ids)

    podcasts = podcasts.order_by('-times_picked', 'name')

    paginator = Paginator(podcasts, 15)
    page = request.GET.get('page')
    try:
        paged = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        paged = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        paged = paginator.page(paginator.num_pages)

    context['count'] = paginator.count

    # past = timezone.now() - datetime.timedelta(days=365)
    episodes = Episode.objects.filter(
        podcast__in=paged,
        # published__gte=past,
    ).values(
        'podcast_id',
    ).annotate(
        duration=Sum('duration'),
        count=Count('podcast_id'),
    )
    episode_counts = {}
    episode_seconds = {}
    for x in episodes:
        episode_counts[x['podcast_id']] = x['count']
        episode_seconds[x['podcast_id']] = x['duration']

    items = []
    for podcast in paged:
        item = {
            'id': podcast.id,
            'name': podcast.name,
            'image': (
                podcast.image and
                podcast.get_thumbnail_url('348x348') or
                None
            ),
            'times_picked': podcast.times_picked,
            'slug': podcast.get_or_create_slug(),
            'last_fetch': (
                podcast.last_fetch and
                podcast.last_fetch.isoformat() or
                None
            ),
            'modified': podcast.modified.isoformat(),
            'episode_count': episode_counts.get(podcast.id, 0),
            'episode_seconds': episode_seconds.get(podcast.id, 0),
        }
        items.append(item)

    context['items'] = items

    pagination = {
        'has_previous': paged.has_previous(),
        'has_next': paged.has_next(),
        'number': paged.number,
        'num_pages': paginator.num_pages,
    }
    if pagination['has_previous']:
        pagination['previous_page_number'] = paged.previous_page_number()
    if pagination['has_next']:
        pagination['next_page_number'] = paged.next_page_number()
    context['pagination'] = pagination
    return http.JsonResponse(context)


def add(request):
    return redirect('https://podcasttime.io', permanent=True)


def picks(request):
    return redirect('https://podcasttime.io/picks', permanent=True)


def picks_data(request):
    context = {}
    qs = Picked.objects.all().order_by('-modified')

    paginator = Paginator(qs, 5)  # XXX make this something bigger like 15
    page = request.GET.get('page')
    try:
        paged = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        paged = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        paged = paginator.page(paginator.num_pages)

    items = []
    # XXX ALL of this needs to be optimized
    for pick in paged:
        podcasts = []
        for podcast in pick.podcasts.all().order_by('-times_picked'):
            podcasts.append({
                'name': podcast.name,
                'image': (
                    podcast.image and
                    podcast.get_thumbnail_url('348x348') or
                    None
                ),
                'times_picked': podcast.times_picked,
                'id': podcast.id,
                'slug': podcast.get_or_create_slug(),
            })
        items.append({'podcasts': podcasts, 'id': pick.id})
    context['items'] = items

    pagination = {
        'has_previous': paged.has_previous(),
        'has_next': paged.has_next(),
        'number': paged.number,
        'num_pages': paginator.num_pages,
    }
    if pagination['has_previous']:
        pagination['previous_page_number'] = paged.previous_page_number()
    if pagination['has_next']:
        pagination['next_page_number'] = paged.next_page_number()
    context['pagination'] = pagination

    return http.JsonResponse(context)


def podcast(request, id, slug=None):
    podcast = get_object_or_404(Podcast, id=id)
    return redirect(
        'https://podcasttime.io/podcasts/{}/{}'.format(
            podcast.id,
            podcast.slug,
        ),
        permanent=True
    )


def podcast_data(request, id, slug=None):
    podcast = get_object_or_404(Podcast, id=id, slug__iexact=slug)
    context = {}
    context.update({
        'id': podcast.id,
        'slug': podcast.slug,
        'name': podcast.name,
        'url': podcast.url,
        'image_url': podcast.image_url,
        'times_picked': podcast.times_picked,
        'total_seconds': podcast.total_seconds,
        'last_fetch': podcast.last_fetch,
        'latest_episode': podcast.latest_episode,
        'modified': podcast.modified,
    })
    if podcast.error:
        context['_has_error'] = True
    if (
        not podcast.last_fetch or
        podcast.last_fetch < timezone.now() - datetime.timedelta(days=7)
    ):
        cache_key = 'updating:episodes:{}'.format(podcast.id)
        if not cache.get(cache_key):
            cache.set(cache_key, True, 60)
            download_episodes_task.delay(podcast.id)
            context['_updating'] = True
    episodes = Episode.objects.filter(
        podcast=podcast
    ).order_by('-published')
    if podcast.image and is_html_document(podcast.image.path):
        print("Found a podcast.image that wasn't an image")
        podcast.image = None
        podcast.save()
        redownload_podcast_image.delay(podcast.id)
    elif not podcast.image and podcast.image_url:
        redownload_podcast_image.delay(podcast.id)

    if podcast.itunes_lookup is None:
        fetch_itunes_lookup.delay(podcast.id)

    if not episodes.exists():
        download_episodes_task.delay(podcast.id)
    context['episodes_count'] = episodes.count()
    context['episodes'] = []
    for episode in episodes:
        context['episodes'].append({
            'duration': episode.duration,
            'published': episode.published,
            'guid': episode.guid,
        })
    try:
        thumb = podcast.get_thumbnail('348x348')
        context['thumb'] = {
            'url': thumb.url,
            'width': thumb.width,  # XXX is this ever used?!
            'height': thumb.height,
        }
    except IOError:
        # image is so busted it can't be turned into a thumbnail
        podcast.image = None
        podcast.save()
        context['thumb'] = None
        redownload_podcast_image.delay(podcast.id)
    return http.JsonResponse(context)


@cache_page(60 * 60)
def general_stats(request, what):
    context = {}
    if what == 'numbers':
        numbers = {}
        numbers['podcasts'] = Podcast.objects.all().count()
        numbers['picks'] = Picked.objects.all().count()
        numbers['episodes'] = Episode.objects.all().count()
        numbers['total_hours'] = int(Episode.objects.all().aggregate(
            count=Sum('duration')
        )['count'] / 3600)
        context['numbers'] = numbers
    else:
        raise NotImplementedError(what)
    return http.JsonResponse(context)
