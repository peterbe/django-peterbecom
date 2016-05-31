import datetime

from django.utils import timezone
from django.utils.timesince import timesince

from django_jinja import library


@library.global_function
def show_duration(duration):
    now = timezone.now()
    then = now + datetime.timedelta(seconds=duration)
    return timesince(now, then)
