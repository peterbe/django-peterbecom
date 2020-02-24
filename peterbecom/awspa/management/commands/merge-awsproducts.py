from django.db.models import Count

from peterbecom.base.basecommand import BaseCommand
from peterbecom.awspa.models import AWSProduct


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=10)

    def _handle(self, **options):
        limit = int(options["limit"])

        for x in (
            AWSProduct.objects.all()
            .values("asin")
            .annotate(count=Count("asin"))
            .filter(count__gt=1)
            .order_by("-count")[:limit]
        ):
            self.merge_asin(x["asin"])

    def merge_asin(self, asin):
        products = AWSProduct.objects.filter(asin=asin)
        assert products.count() > 1
        best = None
        print("ASIN", asin)
        best_keywords = None
        for product in products.order_by("-modify_date"):
            if best is None:
                best = product
                best_keywords = set(product.keywords)
            else:
                # print(
                #     "COMPARE",
                #     set(product.keywords),
                #     "BEST:",
                #     best_keywords,
                #     set(product.keywords) - best_keywords,
                # )
                for keyword in set(product.keywords) - best_keywords:
                    best.keywords.append(keyword)
                    best.save()
                    best_keywords.add(keyword)
                print("DELETE:", repr(product))
                product.delete()
        print("BEST:", repr(best), best.keywords)
