import re

from django.contrib.syndication.views import Feed
from django.utils import timezone

from peterbecom.plog.models import BlogItem

from .utils import make_categories_q, parse_ocs_to_categories

smart_static_urls = re.compile(r'src="//')


class PlogFeed(Feed):
    title = "Peterbe.com"
    description = "Stuff in Peter's head"
    link = "/rss.xml"

    def get_object(self, request, oc):
        if request.GET.get("oc"):
            if not oc:
                oc = ""
            oc += "/".join("oc-%s" % x for x in request.GET.getlist("oc"))
        if not oc:
            return
        return parse_ocs_to_categories(oc)

    def items(self, categories):
        qs = BlogItem.objects.filter(pub_date__lt=timezone.now())
        if categories:
            cat_q = make_categories_q(categories)
            qs = qs.filter(cat_q)

        return qs.order_by("-pub_date")[:10]

    def item_title(self, item):
        return item.title

    def item_pubdate(self, item):
        return item.pub_date

    def item_description(self, item):
        summary = item.summary
        if not summary:
            summary = item.rendered
            # content that has
            #  <img src="//aoisjdeqwd.cloudfront/oijsdfa.jpg"
            # should default to
            #  <img src="http://aoisjdeqwd.cloudfront/oijsdfa.jpg"
            summary = smart_static_urls.sub('src="https://', summary)
            # this is to please
            # http://validator.w3.org/feed/check.cgi?url=http%3A%2F%2Fwww.peterbe.com%2Frss.xml
        return summary
