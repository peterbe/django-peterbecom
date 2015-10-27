from django.shortcuts import render
from django.conf import settings
from django.views.decorators.cache import never_cache, cache_page
from django.utils import timezone


def index(request):

    def cdn_wrap(absolute_path):
        return '{}://{}{}'.format(
            request.is_secure() and 'https' or 'http',
            settings.CDNTHIS_CLOUDFRONT_DOMAIN,
            absolute_path,
        )

    context = {
        'page_title': 'CDN This!',
        'cdn_wrap': cdn_wrap,
    }
    return render(request, 'cdnthis/index.html', context)


@never_cache
def nocaching(request):
    context = {
        'now': timezone.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    }
    return render(request, 'cdnthis/nocaching.html', context)


@cache_page(60 * 60 * 24)
def cached(request):
    context = {
        'now': timezone.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    }
    return render(request, 'cdnthis/cached.html', context)
