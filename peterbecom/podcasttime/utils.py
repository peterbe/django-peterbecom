import codecs
import os
import hashlib
import time
import json
import re
import random
import collections
from urllib.parse import urlparse
from xml.parsers.expat import ExpatError

import xmltodict
import feedparser
import requests
import subprocess
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

_MEDIA_FILE = os.path.join(
    os.path.dirname(__file__), '.mediacache.json'
)

_CACHE = os.path.join(
    os.path.dirname(__file__), '.downloadcache'
)


class NotFound(Exception):
    """when something can't be downloaded"""


class NotXMLResponse(Exception):
    """happens when you expect an XML feed as a response but get something
    else."""


def requests_retry_session(
    retries=4,
    backoff_factor=0.4,
    status_forcelist=(500, 502, 504),
    session=None,
):
    """Opinionated wrapper that creates a requests session with a
    HTTPAdapter that sets up a Retry policy that includes connection
    retries.

    If you do the more naive retry by simply setting a number. E.g.::

        adapter = HTTPAdapter(max_retries=3)

    then it will raise immediately on any connection errors.
    Retrying on connection errors guards better on unpredictable networks.
    From http://docs.python-requests.org/en/master/api/?highlight=retries#requests.adapters.HTTPAdapter
    it says: "By default, Requests does not retry failed connections."

    The backoff_factor is documented here:
    https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#urllib3.util.retry.Retry
    A default of retries=3 and backoff_factor=0.3 means it will sleep like::

        [0.3, 0.6, 1.2]
    """  # noqa
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def get_base_url(url):
    parsed = urlparse(url)
    return '{}://{}'.format(parsed.scheme, parsed.netloc)


def is_html_document(filepath):
    command = ['file', '-b', filepath]
    out, err = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate(timeout=60)
    return out and b'HTML document text' in out


def wrap_subprocess(command):
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
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
        try:
            out, err = wrap_subprocess(command)
        except subprocess.TimeoutExpired as exception:
            return None, exception
        REGEX = re.compile('Duration: (\d+):(\d+):(\d+).(\d+)')
        matches = REGEX.findall(err.decode('utf-8'))
        try:
            found, = matches
        except ValueError:
            print("SUBPROCESS ERROR")
            print(repr(err))
            print
            return None, err.decode('utf-8')
        hours = int(found[0])
        minutes = int(found[1])
        minutes += hours * 60
        seconds = int(found[2])
        seconds += minutes * 60
        duration = seconds + minutes * 60 + hours * 60 * 60
        _cache[media_url] = duration
        with open(_MEDIA_FILE, 'w') as f:
            json.dump(_cache, f, indent=4)
    return _cache[media_url], None


def realistic_request(
    url,
    verify=True,
    no_user_agent=False,
    timeout=None,
    session=None,
):
    headers = {
        'Accept': (
            'text/html,application/xhtml+xml,application/xml,text/xml'
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
    }
    if no_user_agent:
        headers.pop('User-Agent')
    session = requests_retry_session(session=session)
    return session.get(url, headers=headers, verify=verify, timeout=timeout)


def download(
    url,
    gently=False,
    refresh=False,
    no_user_agent=False,
    expect_xml=False,
    timeout=None,
    session=None,
):
    if not os.path.isdir(_CACHE):
        os.mkdir(_CACHE)
    key = hashlib.md5(url.encode('utf-8')).hexdigest()
    if no_user_agent:
        key += 'nouseragent'
    fp = os.path.join(_CACHE, key)
    if os.path.isfile(fp):
        age = time.time() - os.stat(fp).st_mtime
        if age > 60 * 60 * 24:
            os.remove(fp)
    if not os.path.isfile(fp) or refresh:
        print("* requesting", url)
        r = realistic_request(
            url,
            no_user_agent=no_user_agent,
            session=session,
        )
        if r.status_code == 200:
            if expect_xml and not (
                'xml' in r.headers.get('Content-Type', '') or '<rss' in r.text
            ):
                raise NotXMLResponse(r.headers['Content-Type'])
            with codecs.open(fp, 'w', 'utf8') as f:
                f.write(r.text)
            if gently:
                time.sleep(random.randint(1, 4))
        else:
            raise NotFound('{} - {}'.format(
                r.status_code, url
            ))

    with codecs.open(fp, 'r', 'utf8') as f:
        return f.read()


def get_image_url(rss_url):
    try:
        xml = download(rss_url, expect_xml=True)
    except NotXMLResponse:
        xml = download(rss_url, expect_xml=True, no_user_agent=True)
    d = feedparser.parse(xml)

    if xml.startswith(u'\xef\xbb\xbf<?xml'):
        # some buggy XML feed has this
        xml = xml.replace(u'\xef\xbb\xbf<?xml', u'<?xml')

    try:
        image_url = d.feed.itunes_image
        print('itunes_image', image_url)
    except AttributeError:
        image_url = None
        if xml.split('<item')[0].find('<itunes:image') > -1:
            try:
                parsed = xmltodict.parse(xml)
                print('parsed')
            except ExpatError:
                print("BAD XML!!")
                with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                    f.write(xml)
                    print("WROTE /tmp/xml.xml")
                raise
            try:
                if isinstance(
                    parsed['rss']['channel']['itunes:image'],
                    str
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
                elif isinstance(
                    parsed['rss']['channel']['itunes:image'],
                    collections.Mapping
                ):
                    try:
                        image_url = (
                            parsed['rss']['channel']['itunes:image']['@href']
                        )
                    except KeyError:
                        image_url = (
                            parsed['rss']['channel']['itunes:image']['url']
                        )

            except (KeyError, TypeError, KeyError):
                print("PARSED IS WEIRD")
                # print parsed
                print(rss_url)
                with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                    f.write(xml)
                    print("WROTE /tmp/xml.xml")
                raise

        if not image_url:
            try:
                image_url = d.feed.image['href']
            except AttributeError:
                print("NO IMAGE")
                # print d.feed
                try:
                    print("IMAGE??", d.feed.image)
                    print("IMAGE.URL??", d.feed.image['url'])
                    raise
                except AttributeError:
                    # doesn't even have a feed.image
                    return

    if image_url:
        ext = image_url.split('.')[-1].lower()
        if ext not in ('png', 'jpeg', 'jpg', 'gif', 'bmp'):
            # Don't want your kind here!
            return None
    return image_url


def get_podcast_metadata(rss_url, swallow_requests_exceptions=False):
    metadata = {}
    try:
        try:
            xml = download(rss_url, expect_xml=True)
        except NotXMLResponse:
            xml = download(rss_url, expect_xml=True, no_user_agent=True)
    except requests.exceptions.RequestException:
        if swallow_requests_exceptions:
            return
        raise

    d = feedparser.parse(xml)

    for key in ('link', 'subtitle', 'summary'):
        if d['feed'].get(key):
            metadata[key] = d['feed'][key]

    if (
        metadata.get('subtitle') and
        metadata.get('subtitle') == metadata.get('summary')
    ):
        del metadata['subtitle']

    return metadata


if __name__ == '__main__':
    import sys
    for arg in sys.argv[1:]:
        print(get_image_url(arg))
