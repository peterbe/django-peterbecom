import datetime
import hashlib

from django import http
from django.shortcuts import render
from django.db.models import Sum
from django.core.cache import cache
from django.conf import settings

from sorl.thumbnail import get_thumbnail

from peterbecom.apps.podcasttime.models import Podcast, Episode
from peterbecom.apps.podcasttime.forms import CalendarDataForm
from peterbecom.apps.podcasttime.utils import is_html_document
from peterbecom.apps.podcasttime.tasks import (
    download_episodes_task,
    redownload_podcast_image,
)


def index(request):
    context = {}
    context['page_title'] = "Podcast Time"
    context['podcasts'] = Podcast.objects.all()
    context['episodes'] = Episode.objects.all()
    total_seconds = Episode.objects.all().aggregate(
        Sum('duration')
    )['duration__sum']
    context['total_hours'] = total_seconds / 3600
    return render(request, 'podcasttime/index.html', context)


def find(request):
    if not request.GET.get('q'):
        return http.HttpResponseBadRequest('no q')
    q = request.GET['q']
    cache_key = 'podcastfind:' + hashlib.md5(q).hexdigest()
    items = []
    found = []
    sql = (
        "to_tsvector('english', name) @@ "
        "to_tsquery('english', %s)"
    )
    podcasts = Podcast.objects.all().extra(
        where=[sql],
        params=[q]
    )[:10]
    for podcast in podcasts[:10]:
        found.append(podcast)
    podcasts = Podcast.objects.filter(name__istartswith=q).exclude(
        id__in=[x.id for x in found]
    )
    for podcast in podcasts[:10]:
        found.append(podcast)
    if len(q) > 1:
        podcasts = Podcast.objects.filter(name__icontains=q).exclude(
            id__in=podcasts
        )
        for podcast in podcasts[:10]:
            found.append(podcast)

    def episodes_meta(podcast):
        episodes_cache_key = 'episodes-meta-%s' % podcast.id
        meta = cache.get(episodes_cache_key)
        if meta is None:
            episodes = Episode.objects.filter(podcast=podcast)
            episodes_count = episodes.count()
            total_hours = None
            if episodes_count:
                total_seconds = episodes.aggregate(
                    Sum('duration')
                )['duration__sum']
                if total_seconds:
                    total_hours = total_seconds / 3600.0
            else:
                download_episodes_task.delay(podcast.id)
            meta = {
                'count': episodes_count,
                'total_hours': total_hours,
            }
            cache.set(episodes_cache_key, meta, 60 * 60 * 24)
        return meta

    items = cache.get(cache_key)
    if items is None:
        items = []
        for podcast in found:

            if podcast.image and is_html_document(podcast.image.path):
                print "Found a podcast.image that wasn't an image"
                podcast.image = None
                podcast.save()
            if podcast.image:
                if podcast.image.size < 1000:
                    print "IMAGE LOOKS SUSPICIOUS"
                    print podcast.image_url
                    print repr(podcast), podcast.id
                    print podcast.url
                    print repr(podcast.image.read())
                    podcast.download_image()
            thumb_url = None
            if podcast.image:
                try:
                    thumb_url = get_thumbnail(
                        podcast.image,
                        '100x100',
                        quality=81,
                        upscale=False
                    ).url
                except IOError:
                    import sys
                    print "BAD IMAGE!"
                    print sys.exc_info()
                    print repr(podcast.image)
                    print repr(podcast), podcast.url
                    print
                    podcast.image = None
                    podcast.save()
                    redownload_podcast_image.delay(podcast.id)
            else:
                redownload_podcast_image.delay(podcast.id)

            meta = episodes_meta(podcast)
            episodes_count = meta['count']
            total_hours = meta['total_hours']
            items.append({
                'id': podcast.id,
                'name': podcast.name,
                'image_url': thumb_url,
                'episodes': episodes_count,
                'hours': total_hours,
            })

        cache.set(cache_key, items, 60 * 60 * int(settings.DEBUG))

    return http.JsonResponse({'items': items})


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
