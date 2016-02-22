import codecs
import os
import hashlib
import time
import random
from xml.parsers.expat import ExpatError

import xmltodict
import feedparser
import requests


_CACHE = os.path.join(
    os.path.dirname(__file__), '.downloadcache'
)


def realistic_request(url, verify=True):
    return requests.get(url, headers={
        'Accept': (
            'text/html,application/xhtml+xml,application/xml'
            ';q=0.9,*/*;q=0.8'
        ),
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:46.0) '
            'Gecko/20100101 Firefox/46.0'
        ),
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Host': urlparse.urlparse(url).netloc,
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }, verify=verify)


def download(url):
    if not os.path.isdir(_CACHE):
        os.mkdir(_CACHE)
    key = hashlib.md5(url).hexdigest()
    fp = os.path.join(_CACHE, key)
    if os.path.isfile(fp):
        age = time.time() - os.stat(fp).st_mtime
        if age > 60 * 60 * 24:
            os.remove(fp)
    if not os.path.isfile(fp):
        print "* requesting", url
        r = realistic_request(url)
        if r.status_code == 200:
            with codecs.open(fp, 'w', 'utf8') as f:
                f.write(r.text)
            time.sleep(random.randint(1, 3))
        else:
            raise Exception(r.status_code)

    with codecs.open(fp, 'r', 'utf8') as f:
        return f.read()


def get_image_url(rss_url):
    xml = download(rss_url)
    d = feedparser.parse(xml)

    if xml.startswith(u'\xef\xbb\xbf<?xml'):
        # some buggy XML feed has this
        xml = xml.replace(u'\xef\xbb\xbf<?xml', u'<?xml')

    try:
        image_url = d.feed.itunes_image
    except AttributeError:
        image_url = None
        if xml.split('<item')[0].find('<itunes:image') > -1:
            try:
                parsed = xmltodict.parse(xml)
            except ExpatError:
                print "BAD XML!!"
                with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                    f.write(xml)
                    print "WROTE /tmp/xml.xml"
                raise
            try:
                if isinstance(
                    parsed['rss']['channel']['itunes:image'],
                    basestring
                ):
                    image_url = (
                        parsed['rss']['channel']['itunes:image']
                    )
                elif isinstance(
                    parsed['rss']['channel']['itunes:image'],
                    list
                ):
                    image_url = (
                        parsed['rss']['channel']['itunes:image'][0]['@href']
                    )
                else:
                    image_url = (
                        parsed['rss']['channel']['itunes:image']['@href']
                    )
            except (KeyError, TypeError, KeyError):
                print "PARSED IS WEIRD"
                print parsed
                print rss_url
                with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                    f.write(xml)
                    print "WROTE /tmp/xml.xml"
                raise

        if not image_url:
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
                    return

    return image_url

if __name__ == '__main__':
    import sys
    print download(sys.argv[1])
