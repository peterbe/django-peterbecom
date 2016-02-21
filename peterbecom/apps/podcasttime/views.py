import hashlib

from django import http
from django.shortcuts import render
from django.db.models import Sum
from django.core.cache import cache
from django.conf import settings

from sorl.thumbnail import get_thumbnail

from peterbecom.apps.podcasttime.models import Podcast, Episode


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
    podcasts = Podcast.objects.filter(name__istartswith=q)
    for podcast in podcasts[:10]:
        found.append(podcast)
    podcasts = Podcast.objects.filter(name__icontains=q).exclude(
        id__in=podcasts
    )
    for podcast in podcasts[:10]:
        found.append(podcast)

    items = cache.get(cache_key)
    if items is None:
        items = []
        for podcast in found:
            if podcast.image:
                if podcast.image.size < 1000:
                    print "IMAGE LOOKS SUSPICIOUS"
                    print podcast.image_url
                    print repr(podcast), podcast.id
                    print podcast.url
                    print repr(podcast.image.read())
                    podcast.download_image()

            episodes = Episode.objects.filter(podcast=podcast)
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
            total_hours = None
            episodes_count = episodes.count()
            # print repr(podcast.name), episodes.count()
            if episodes_count:
                total_seconds = episodes.aggregate(
                    Sum('duration')
                )['duration__sum']
                if total_seconds:
                    total_hours = total_seconds / 3600.0
            items.append({
                'id': podcast.id,
                'name': podcast.name,
                'image_url': thumb_url,
                'episodes': episodes_count,
                'hours': total_hours,
            })

        cache.set(cache_key, items, 60 * 60 * int(settings.DEBUG))

    return http.JsonResponse({'items': items})
