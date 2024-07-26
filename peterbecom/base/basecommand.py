import copy
import datetime
import os
import sys
import time
import traceback
from io import StringIO

import rollbar
from django.conf import settings
from django.core.management.base import BaseCommand as DjangoBaseCommand

from peterbecom.base.models import CommandRun

ROLLBAR_ENABLED = settings.ROLLBAR and settings.ROLLBAR.get("enabled", True)
if ROLLBAR_ENABLED:
    rollbar.init(settings.ROLLBAR["access_token"], settings.ROLLBAR["environment"])


class BaseCommand(DjangoBaseCommand):
    def __init__(self, *args, **kwargs):
        super(BaseCommand, self).__init__(*args, **kwargs)
        self._outs = []
        self._notices = []
        self._warnings = []
        self._errors = []

        if not getattr(self, "STYLE", None):
            # e.g. Django < 1.10
            self.style.SUCCESS = lambda x: x
            self.style.NOTICE = self.style.SUCCESS
            self.style.WARNING = self.style.SUCCESS
            self.style.ERROR = self.style.SUCCESS

    @staticmethod
    def clean_options(kwargs):
        # gently remove all the standard django management command keys
        copied = copy.deepcopy(kwargs)
        copied.pop("pythonpath", None)
        copied.pop("no_color", None)
        copied.pop("settings", None)
        copied.pop("verbosity", None)
        copied.pop("traceback", None)
        return copied

    def handle(self, **options):
        # self._handle(**options)
        try:
            self._handle(**options)
        except Exception:
            if not settings.DEBUG:
                if ROLLBAR_ENABLED:
                    rollbar.report_exc_info()
            raise

    def execute(self, *args, **kwargs):
        app = self.__class__.__module__.split(".")[-4]
        command = self.__class__.__module__.split(".")[-1]
        if getattr(settings, "PAUSE_ALL_COMMANDS", False) and not os.environ.get(
            "IGNORE_PAUSE_ALL_COMMANDS"
        ):
            self.notice("ALL COMMANDS PAUSED! ({})".format(command))
            return
        command_fn = os.path.join(os.path.dirname(__file__), command + ".commandlock")
        if os.path.isfile(command_fn):
            # But how old is that file?
            age = time.time() - os.stat(command_fn).st_mtime
            if age > 60 * 60 * 24:
                self.notice("REMOVED because it was too old {}".format(command_fn))
                os.remove(command_fn)
            else:
                self.notice("LOCKED! ({})".format(command_fn))
                return

        with open(command_fn, "w") as f:
            f.write("{}\n".format(time.time()))
        try:
            t0 = time.time()
            exception = None
            notes = None
            return super(BaseCommand, self).execute(*args, **kwargs)
        except Exception:
            etype, evalue, tb = sys.exc_info()
            out = StringIO()
            traceback.print_exception(etype, evalue, tb, file=out)
            exception = out.getvalue()
        finally:
            t1 = time.time()
            try:
                os.remove(command_fn)
            except OSError:
                pass
            try:
                notes = StringIO()
                _logs = (
                    ("Errors:", self._errors),
                    ("Notices:", self._notices),
                    ("Warnings:", self._warnings),
                    ("General:", self._outs),
                )
                for label, array in _logs:
                    if array:
                        notes.write(label)
                        notes.write("\n")
                        for row in array:
                            notes.write("\t" + " ".join(str(x) for x in row))
                            notes.write("\n")
                        notes.write("\n")
                notes = notes.getvalue().strip() or None
                CommandRun.objects.create(
                    command=command,
                    app=app,
                    duration=datetime.timedelta(seconds=t1 - t0),
                    notes=notes,
                    exception=exception,
                    options=self.clean_options(kwargs),
                )
            except Exception as exc:
                print("Panicly failed to log CommandRun {!r}".format(exc))

    def out(self, *strs):
        self._outs.append(strs)
        self.stdout.write(self.style.SUCCESS(" ".join(str(x) for x in strs)))

    def notice(self, *strs):
        self._notices.append(strs)
        self.stdout.write(self.style.NOTICE(" ".join(str(x) for x in strs)))

    def warning(self, *strs):
        self._warnings.append(strs)
        self.stdout.write(self.style.WARNING(" ".join(str(x) for x in strs)))

    def error(self, *strs):
        self._errors.append(strs)
        self.stdout.write(self.style.ERROR(" ".join(str(x) for x in strs)))
