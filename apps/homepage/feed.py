import datetime
import re
from django.contrib.syndication.views import Feed
from apps.plog.models import BlogItem

class PlogFeed(Feed):
    title = "Peterbe.com"
    description = "Peter Bengtssons's personal homepage about little things that concern him."
    link = "/rss.xml"

    def items(self):
        return (BlogItem.objects
                .filter(pub_date__lt=datetime.datetime.utcnow())
                .order_by('-pub_date'))[:10]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        summary = item.summary
        if not summary:
            summary = item.rendered
            print re.findall('<\!--\s*split\s*-->', summary)
        return summary
