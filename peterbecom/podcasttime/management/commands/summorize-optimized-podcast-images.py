import re
import os
import time

from django.conf import settings
from django.db.models import Q
from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):
    def _handle(self, **options):

        self.parsers = {
            ".mozjpeged": self._mozjpeged,
            ".optimized": self._optimized,
            ".pngquanted": self._pngquanted,
            ".pillow": self._pillow,
            ".guetzlied": self._guetzlied,
        }
        all_log_files = self._find_all_logfiles(
            os.path.abspath(os.path.join(settings.MEDIA_ROOT, "podcasts"))
        )
        savings = {}
        most_recent = {}
        for logfile in all_log_files:
            _, ext = os.path.splitext(logfile)
            parser = self.parsers[ext]
            if ext not in savings:
                savings[ext] = []
            with open(logfile) as f:
                content = f.read().strip()
                if not content:
                    print("Empty file!", logfile)
                    continue
                saved = parser(content)
                if saved is not None and saved > 0:
                    savings[ext].append(saved)

                    previous = most_recent.get(ext)
                    this_one = os.stat(logfile).st_mtime
                    if previous is None or this_one > previous:
                        most_recent[ext] = this_one

        qs = Podcast.objects.filter(
            Q(image__iendswith=".jpg") | Q(image__iendswith=".png")
        )
        print(format(qs.count(), ","), "total Podcast images")
        total = 0
        for ext in savings:
            print(ext)
            length = len(savings[ext])
            print("\t", format(length, ","), "times")
            sum_ = sum(savings[ext])
            total += sum_
            print("\t", filesizeformat(sum_), "total")
            print("\t", filesizeformat(sum_ / length), "average")
            age = time.time() - most_recent[ext]
            if age > 60 * 60 * 24:
                age = "{:.1f} days".format(age / (3600 * 24))
            elif age > 60 * 60:
                age = "{:.1f} hours".format(age / 3600)
            elif age > 60:
                age = "{:.1f} minutes".format(age / 60)
            else:
                age = "{:.1f} seconds".format(age)
            print("\t", "most recent", age, "ago")

        print("\nIN TOTAL... {}\n".format(filesizeformat(total)))

    @staticmethod
    def _parse_filesize(number, unit):
        number = float(number)
        if unit == "KB":
            number *= 1024
        elif unit == "MB":
            number *= 1024 * 1024
        elif unit == "bytes":
            pass
        else:
            raise NotImplementedError(unit)
        return number

    def _mozjpeged(self, content):
        found = re.findall(r"From ([\d,]+) bytes to ([\d,]+) bytes", content)
        try:
            before, after = [int(x.replace(",", "")) for x in found[0]]
        except IndexError:
            try:
                found = re.findall(
                    r"From ([\d\.]+)\s+(\w+) to ([\d\.]+)\s+(\w+)", content
                )[0]
                before = self._parse_filesize(found[0], found[1])
                after = self._parse_filesize(found[2], found[3])
            except IndexError:
                print(("CONTENT", content))
                raise Exception(content)
        return before - after

    def _optimized(self, content):
        found = re.findall(r"\((([\d,]+)\sbytes)\)", content)
        if not found:
            found = re.findall(r"From (\d+) to (\d+)", content)[0]
        before, after = [int(x[1].replace(",", "")) for x in found]
        return before - after

    def _pngquanted(self, content):
        if content.startswith("skipped because it got larger"):
            return
        # print(repr(content))
        found = re.findall(r"From ([\d\.]+)\s+(\w+) to ([\d\.]+)\s+(\w+)", content)[0]
        before = self._parse_filesize(found[0], found[1])
        after = self._parse_filesize(found[2], found[3])
        return before - after

    def _pillow(self, content):
        try:
            found = re.findall(r"From ([\d\.]+)\s+(\w+) to ([\d\.]+)\s+(\w+)", content)[
                0
            ]
        except IndexError:
            found = re.findall(
                r"From ([\d\.]+)\s+(\w+) bytes to ([\d\.]+)\s+(\w+) bytes", content
            )[0]
        before = self._parse_filesize(found[0], found[1])
        after = self._parse_filesize(found[2], found[3])
        return before - after

    def _guetzlied(self, content):
        if content.startswith("YUVColorError"):
            return
        # print(repr(content))
        try:
            found = re.findall(r"From ([\d\.]+)\s+(\w+) to ([\d\.]+)\s+(\w+)", content)[
                0
            ]
            before = self._parse_filesize(found[0], found[1])
            after = self._parse_filesize(found[2], found[3])
        except IndexError:
            try:
                found = re.findall(
                    r"From ([\d\.]+)\s+(\w+) bytes to ([\d\.]+)\s+(\w+) bytes", content
                )[0]
                before = self._parse_filesize(found[0], found[1])
                after = self._parse_filesize(found[2], found[3])
            except IndexError:
                found = re.findall(r"From ([\d,]+) bytes to ([\d,]+) bytes", content)
                before, after = [int(x.replace(",", "")) for x in found[0]]
        return before - after

    def _find_all_logfiles(self, directory):
        assert os.path.isdir(directory)
        here = []
        for name in os.listdir(directory):
            fp = os.path.join(directory, name)
            if os.path.isdir(fp):
                here.extend(self._find_all_logfiles(fp))
            else:
                _, ext = os.path.splitext(fp)
                if ext in self.parsers:
                    here.append(fp)
        return here
