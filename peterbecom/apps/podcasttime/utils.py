import codecs
import os
import hashlib
import time
import json
import re
import random
from xml.parsers.expat import ExpatError

import xmltodict
import feedparser
import requests
import subprocess32


_MEDIA_FILE = os.path.join(
    os.path.dirname(__file__), '.mediacache.json'
)

_CACHE = os.path.join(
    os.path.dirname(__file__), '.downloadcache'
)


def is_html_document(filepath):
    command = ['file', '-b', filepath]
    out, err = subprocess32.Popen(
        command,
        stdout=subprocess32.PIPE,
        stderr=subprocess32.PIPE
    ).communicate(timeout=60)
    return out and 'HTML document text' in out


def wrap_subprocess(command):
    print command
    return subprocess32.Popen(
        command,
        stdout=subprocess32.PIPE,
        stderr=subprocess32.PIPE
    ).communicate(timeout=60 * 2)


def parse_duration_ffmpeg(media_url):
    try:
        with open(_MEDIA_FILE) as f:
            _cache = json.load(f)
    except IOError:
        _cache = {}
    except ValueError:
        # the json file is corrupted
        _cache = {}
    if media_url not in _cache:
        command = ['ffmpeg', '-i', media_url]
        out, err = wrap_subprocess(command)
        REGEX = re.compile('Duration: (\d+):(\d+):(\d+).(\d+)')
        matches = REGEX.findall(err)
        # if matches:
        try:
            found, = matches
        except ValueError:
            print err
            return
        hours = int(found[0])
        minutes = int(found[1])
        minutes += hours * 60
        seconds = int(found[2])
        seconds += minutes * 60
        duration = seconds + minutes * 60 + hours * 60 * 60
        _cache[media_url] = duration
        with open(_MEDIA_FILE, 'w') as f:
            json.dump(_cache, f, indent=4)
    return _cache[media_url]


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


def download(url, gently=False):
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
            if gently:
                time.sleep(random.randint(1, 4))
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
