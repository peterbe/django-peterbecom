from peterbecom.base.basecommand import BaseCommand
from peterbecom.awspa.models import AWSProduct
from peterbecom.awspa.search import lookup


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--limit', default=10)
        parser.add_argument('--sleep', default=1.1)

    def _handle(self, **options):
        limit = int(options['limit'])
        sleep = float(options['sleep'])
        qs = AWSProduct.objects.exclude(disabled=True)

        def diff(d1, d2, indent=None):
            indent = indent or []
            diffkeys = [k for k in d1 if d1[k] != d2.get(k)]
            for k in diffkeys:
                if isinstance(d1[k], dict):
                    diff(d1[k], d2[k], indent=indent + [k])
                else:
                    print(
                        '.'.join(indent) + '.' + k,
                        ':', d1[k], '->', d2.get(k)
                    )

        for awsproduct in qs.order_by('modify_date')[:limit]:
            print(
                awsproduct.asin,
                awsproduct.modify_date,
                repr(awsproduct.keyword),
                awsproduct.searchindex,
            )
            payload, error = lookup(
                awsproduct.asin,
                sleep=sleep
            )
            diff(awsproduct.payload, payload)

            awsproduct.payload = payload
            awsproduct.save()
            print()
