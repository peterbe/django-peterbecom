import random
from urlparse import urljoin

import pyquery

from django.core.management.base import BaseCommand

from peterbecom.apps.podcasttime.models import Podcast
from peterbecom.apps.podcasttime.utils import download, get_image_url


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        verbose = int(kwargs['verbosity']) >= 2
        only_new = kwargs.get('only_new', True)
        baseurl = args[0]
        html = download(baseurl)
        doc = pyquery.PyQuery(html)
        urls = []
        for a in doc('ul.nav ul.dropdown-menu li a'):
            href = a.attrib['href']
            if '/browse/' in href:
                url = urljoin(baseurl, href)
                urls.append(url)

        max_ = 10
        random.shuffle(urls)
        for url in urls[:max_]:
            self.scrape_index(
                url,
                verbose=verbose,
                max_=max_,
                only_new=only_new,
            )

    def scrape_index(self, url, verbose=False, max_=1000, only_new=False):
        html = download(url)
        doc = pyquery.PyQuery(html)
        links = doc('.thumbnails a')
        shows = []
        for link in links:
            show_url = link.attrib['href']
            show_url = urljoin(url, show_url)
            link = pyquery.PyQuery(link)
            for h4 in link.find('h4'):
                name = h4.text_content()
            shows.append((name, show_url))

        existing_names = Podcast.objects.all().values_list('name', flat=True)

        # XXX might not keep this
        shows = [
            (n, u) for (n, u) in shows
            if n not in existing_names
        ]
        random.shuffle(shows)
        for name, show_url in shows[:max_]:
            rss_url = self.scrape_show(show_url)
            if not rss_url:
                print "Skipping", name, show_url
                continue

            image_url = get_image_url(rss_url)
            if not image_url:
                print "Skipping (no image)", name, rss_url
                continue
            assert '://' in image_url, image_url
            # print "IMAGE_URL", image_url

            try:
                podcast = Podcast.objects.get(name=name)
                podcast.url = rss_url
                podcast.image_url = image_url
                podcast.save()
                created = False
            except Podcast.DoesNotExist:
                podcast = Podcast.objects.create(
                    name=name,
                    url=rss_url,
                    image_url=image_url,
                )
                created = True
            try:
                podcast.download_image()
            except AssertionError:
                if verbose:
                    print "Got an error trying to download the image :("
                    import sys
                    print sys.exc_info()
                    print "IGNORING AND MOVING ON"

            if verbose:
                if created:
                    print "CREATED",
                else:
                    print "NOT NEW",
                print repr(name)

    @staticmethod
    def scrape_show(url):
        html = download(url)
        doc = pyquery.PyQuery(html)
        for a in doc('.sidebar-nav a'):
            for h4 in pyquery.PyQuery(a).find('h4'):
                if h4.text_content() == 'Open RSS feed':
                    rss_url = urljoin(url, a.attrib['href'])
                    return rss_url
