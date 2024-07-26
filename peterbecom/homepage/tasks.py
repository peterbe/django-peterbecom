import datetime

from django.conf import settings
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task

from peterbecom.homepage.models import CatchallURL


@periodic_task(crontab(hour="*", minute="15"))
def delete_rarely_seen_catchall_paths():
    days = settings.MIN_RARELY_SEEN_CATCHALL_DAYS
    old = timezone.now() - datetime.timedelta(days=days)
    qs = CatchallURL.objects.filter(last_seen__lt=old)
    print(f"Old CatchallURLs not seen in {days} days: {qs.count():,}")
    qs.delete()
