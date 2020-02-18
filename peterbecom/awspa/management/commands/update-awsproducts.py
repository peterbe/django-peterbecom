import datetime
import json
import difflib
import time

from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.awspa.models import AWSProduct
from peterbecom.awspa.search import lookup, RateLimitedError


class UpdateAWSError(Exception):
    """A product update failed."""


def diff(d1, d2, indent=None):
    indent = indent or []
    diffkeys = [k for k in d1 if d1[k] != d2.get(k)]
    for k in diffkeys:
        if isinstance(d1[k], dict):
            diff(d1[k], d2[k], indent=indent + [k])
        else:
            print(".".join(indent) + "." + k, ":", d1[k], "->", d2.get(k))


def dumb_diff(d1, d2):
    json1 = json.dumps(d1, indent=2, sort_keys=True).splitlines()
    json2 = json.dumps(d2, indent=2, sort_keys=True).splitlines()

    print(
        "\n".join(difflib.context_diff(json1, json2, fromfile="old", tofile="new", n=2))
    )


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=5)
        parser.add_argument("--sleep", default=7.1)
        parser.add_argument("--without-offers", default=False, action="store_true")

    def _handle(self, **options):
        limit = int(options["limit"])
        sleep = float(options["sleep"])
        old = timezone.now() - datetime.timedelta(hours=12)
        qs = AWSProduct.objects.exclude(disabled=True).filter(modify_date__lt=old)

        if options["without_offers"]:
            qs = qs.exclude(payload__has_key="offers")

        self.notice(qs.count(), "products that can be updated")
        for awsproduct in qs.order_by("modify_date")[:limit]:
            # print(
            #     awsproduct.asin,
            #     awsproduct.modify_date,
            #     repr(awsproduct.keyword),
            #     awsproduct.searchindex,
            # )
            if not awsproduct.paapiv5:
                self.out("Converting", repr(awsproduct), "to paapiv5")
                try:
                    awsproduct.convert_to_paapiv5()
                except RateLimitedError as exception:
                    self.out("RateLimitedError", exception)
                    break
                time.sleep(sleep)
                continue

            try:
                payload, error = lookup(awsproduct.asin, sleep=sleep)
            except RateLimitedError as exception:
                self.out("RateLimitedError", exception)
                break
            if error:
                self.error("Error looking up {!r} ({!r})".format(awsproduct, error))
                if isinstance(error, dict) and error.get("Message"):
                    if "is not a valid value for ItemId" in error["Message"]:
                        # Let's not bother with that AWSProduct any more.
                        awsproduct.disabled = True
                        awsproduct.save()
                        continue
                raise UpdateAWSError(
                    "Error looking up {!r} ({!r})".format(awsproduct, error)
                )

            try:
                diff(awsproduct.payload, payload)
            except (AttributeError, KeyError):
                dumb_diff(awsproduct.payload, payload)

            awsproduct.payload = payload
            awsproduct.paapiv5 = True
            awsproduct.save()
            print()

            time.sleep(sleep)
