import os
import tempfile


CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True


FSCACHE_ROOT = os.path.join(
    tempfile.gettempdir(),
    'test-peterbecom-fscache'
)
