#!/usr/bin/env python
import os, sys
import site
_here = os.path.dirname(__file__)
site.addsitedir(os.path.join(_here, 'vendor'))

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
