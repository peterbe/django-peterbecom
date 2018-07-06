from __future__ import absolute_import, unicode_literals
from celery import shared_task

import datetime


@shared_task
def sample_task(filepath):
    print("Writing to filepath", filepath)
    with open(filepath, "w") as f:
        written = datetime.datetime.utcnow().strftime("%b %H:%M:%S\n")
        print("\t", "wrote", written)
        f.write(written)
