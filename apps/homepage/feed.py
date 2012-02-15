import datetime
import re
from django.contrib.syndication.views import Feed
from apps.plog.models import BlogItem
from .utils import parse_ocs_to_categories, make_categories_q


class PlogFeed(Feed):
    title = "Peterbe.com"
    description = "Peter Bengtssons's personal homepage about little things that concern him."
    link = "/rss.xml"

    def get_object(self, request, oc):
        if not oc:
            return
        return parse_ocs_to_categories(oc)

    def items(self, categories):
        qs = (BlogItem.objects
                .filter(pub_date__lt=datetime.datetime.utcnow()))
        if categories:
            qs = qs.filter(make_categories_q(categories))
        return qs.order_by('-pub_date')[:10]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        summary = item.summary
        if not summary:
            summary = item.rendered
        return summary
