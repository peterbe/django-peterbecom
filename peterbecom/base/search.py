import time

from elasticsearch_dsl import Index
from elasticsearch.exceptions import (
    ConnectionTimeout,
    NotFoundError,
)

from django.conf import settings


index = Index(settings.ES_INDEX)
index.settings(**settings.ES_INDEX_SETTINGS)


def es_retry(callable, *args, **kwargs):
    sleep_time = kwargs.pop('_sleep_time', 1)
    attempts = kwargs.pop('_attempts', 5)
    verbose = kwargs.pop('_verbose', False)
    ignore_not_found = kwargs.pop('_ignore_not_found', False)
    try:
        return callable(*args, **kwargs)
    except (ConnectionTimeout,) as exception:
        if attempts:
            attempts -= 1
            if verbose:
                print("ES Retrying ({} {}) {}".format(
                    attempts,
                    sleep_time,
                    exception
                ))
            time.sleep(sleep_time)
        else:
            raise
    except NotFoundError:
        if not ignore_not_found:
            raise
