import sys

from .base import *  # NOQA
from .local import *  # NOQA


if len(sys.argv) > 1 and sys.argv[1] == 'test':
    # Shuts up excessive logging when running tests
    # import logging
    # logging.disable(logging.WARNING)

    from .test import *  # NOQA

    # # Are you getting full benefit from django-nose?
    # if not os.getenv('REUSE_DB', 'false').lower() in ('true', '1', ''):
    #     print (
    #         "Note!\n\tIf you want much faster tests in local development "
    #         "consider setting the REUSE_DB=1 environment variable.\n"
    #     )
else:
    from .local import *
