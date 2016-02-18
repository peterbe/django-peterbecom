import os
import hashlib

from django import http
from django.shortcuts import render
from django.db.models import Sum
from django.conf import settings
from django.core.cache import cache

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
    if q=='star':
        print podcasts
    for podcast in podcasts[:10]:
        found.append(podcast)
    podcasts = Podcast.objects.filter(name__icontains=q).exclude(
        id__in=podcasts
    )
    for podcast in podcasts[:10]:
        found.append(podcast)

    items = []
    for podcast in found:
        # print dir(podcast.image)
        # print podcast.image.storage
        # print podcast.image.file
        assert os.path.isfile(podcast.image.path), podcast.image.path
        # print os.stat(podcast.image.path).st_size, podcast.image.path
        if os.stat(podcast.image.path).st_size < 1000:
            print "IMAGE LOOKS SUSPICIOUS"
            print repr(podcast), podcast.id
            print repr(open(podcast.image.path).read())
            podcast.download_image()
            print
        # print
        # print
        # break

        episodes = Episode.objects.filter(podcast=podcast)
        thumb = get_thumbnail(
            podcast.image,
            '100x100',
            quality=81,
            upscale=False
        )
        total_hours = None
        episodes_count = episodes.count()
        # print repr(podcast.name), episodes.count()
        if episodes_count:
            total_seconds = episodes.aggregate(Sum('duration'))['duration__sum']
            if total_seconds:
                total_hours = total_seconds / 3600.0
        # if '34a0ed943d320ea8b' in thumb.url:
        #     print repr(podcast)
        #     print repr(podcast.image)
        #     raise Problem
        items.append({
            'name': podcast.name,
            'image_url': thumb.url,
            'episodes': episodes_count,
            'hours': total_hours,
        })

    cache.set(cache_key, items, 60 * 60)

    return http.JsonResponse({'items': items})
