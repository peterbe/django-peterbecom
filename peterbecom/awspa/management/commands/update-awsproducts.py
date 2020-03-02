import datetime
import json
import difflib
import time

from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.awspa.models import AWSProduct
from peterbecom.awspa.search import lookup, RateLimitedError, NothingFoundError


class UpdateAWSError(Exception):
    """A product update failed."""


def diff(d1, d2, indent=None):
    indent = indent or []
    diffkeys = [k for k in d1 if d1[k] != d2.get(k)]
    for k in diffkeys:
        if isinstance(d1[k], dict):
            diff(d1[k], d2[k], indent=indent + [k])
        else:
            key = ".".join(indent + [k])
            print("{}:".format(key))
            dumb_diff(
                d1[k],
                d2.get(k),
                fromfile="old {}".format(key),
                tofile="new {}".format(key),
            )


def dumb_diff(d1, d2, fromfile="old", tofile="new"):
    json1 = json.dumps(d1, indent=2, sort_keys=True).splitlines()
    json2 = json.dumps(d2, indent=2, sort_keys=True).splitlines()

    print(
        "\n".join(
            difflib.context_diff(json1, json2, fromfile=fromfile, tofile=tofile, n=2)
        )
    )


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=10)
        parser.add_argument("--sleep", default=7.1)
        parser.add_argument("--without-offers", default=False, action="store_true")
        parser.add_argument("--not-converted", default=False, action="store_true")

    def _handle(self, **options):
        limit = int(options["limit"])
        sleep = float(options["sleep"])
        old = timezone.now() - datetime.timedelta(hours=12)
        qs = AWSProduct.objects.exclude(disabled=True).filter(modify_date__lt=old)

        if options["without_offers"]:
            qs = qs.exclude(payload__has_key="offers")
        if options["not_converted"]:
            qs = qs.filter(paapiv5=False)

        self.notice(qs.count(), "products that can be updated")
        for i, awsproduct in enumerate(qs.order_by("modify_date")[:limit]):
            print(i + 1, repr(awsproduct))
            # if not awsproduct.paapiv5:
            #     self.out("Converting", repr(awsproduct), "to paapiv5")
            #     try:
            #         awsproduct.convert_to_paapiv5(raise_if_nothing_found=True)
            #     except RateLimitedError as exception:
            #         self.out("RateLimitedError", exception)
            #         break
            #     except NothingFoundError:
            #         self.notice(
            #             "NothingFoundError on {!r}. So, disabling".format(awsproduct)
            #         )
            #         awsproduct.disabled = True
            #         awsproduct.save()

            #     time.sleep(sleep)
            #     continue

            try:
                payload = lookup(awsproduct.asin)
            except RateLimitedError as exception:
                self.out("RateLimitedError", exception)
                break
            except NothingFoundError:
                self.notice(
                    "Nothing found any more for ASIN {}".format(awsproduct.asin)
                )
                awsproduct.disabled = True
                awsproduct.save()
                continue

            # dumb_diff(awsproduct.payload, payload)
            try:
                diff(awsproduct.payload, payload)
            except (AttributeError, KeyError) as e:
                print("EXCEPTION:", e)
                dumb_diff(awsproduct.payload, payload)

            awsproduct.payload = payload
            awsproduct.paapiv5 = True
            awsproduct.save()

            time.sleep(sleep)
