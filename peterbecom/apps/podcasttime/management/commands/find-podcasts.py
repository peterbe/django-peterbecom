import os
import codecs
import random
from urlparse import urljoin
from xml.parsers.expat import ExpatError

import requests
import feedparser
import pyquery
import xmltodict

from django.core.management.base import BaseCommand
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from peterbecom.apps.podcasttime.models import Podcast

from .utils import download


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
            xml = download(rss_url)
            d = feedparser.parse(xml)
            # print d.feed.keys()

            try:
                image_url = d.feed.itunes_image
            except AttributeError:
                # print "No itunes_image"
                # print rss_url
                if xml.split('<item')[0].find('<itunes:image ') > -1:
                    # print
                    # print sorted(d.keys())
                    # print sorted(d.feed.keys())
                    # print d.feed
                    try:
                        parsed = xmltodict.parse(xml)
                    except ExpatError:
                        print "BAD XML!!"
                        with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                            f.write(xml)
                            print "WROTE /tmp/xml.xml"
                        raise
                    try:
                        image_url = (
                            parsed['rss']['channel']['itunes:image']['@href']
                        )
                    except KeyError:
                        print "PARSED"
                        print parsed
                        print rss_url
                        with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                            f.write(xml)
                            print "WROTE /tmp/xml.xml"
                        raise
                try:
                    image_url = d.feed.image['href']
                except AttributeError:
                    print "NO IMAGE"
                    print d.feed
                    try:
                        print "IMAGE??", d.feed.image
                        print "IMAGE.URL??", d.feed.image['url']
                        raise
                    except AttributeError:
                        # doesn't even have a feed.image
                        print "Skipping (no image)", name, rss_url
                        continue
            assert '://' in image_url, image_url

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
            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(requests.get(image_url).content)
            img_temp.flush()
            podcast.image.save(
                os.path.basename(image_url.split('?')[0]),
                File(img_temp)
            )
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
