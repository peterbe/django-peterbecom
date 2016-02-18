import codecs
import os
import hashlib
import time
import random
import urlparse

import requests

_CACHE = os.path.join(
    os.path.dirname(__file__), '.download'
)


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
        r = requests.get(url, headers={
            'Accept': (
                'text/html,application/xhtml+xml,application/xml'
                ';q=0.9,*/*;q=0.8'
            ),
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:46.0) '
                'Gecko/20100101 Firefox/46.0'
            ),
            'Accept-Language': 'en-US,en;q=0.5',
            'Host': urlparse.urlparse(url).netloc,
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        })
        if r.status_code == 200:
            with codecs.open(fp, 'w', 'utf8') as f:
                f.write(r.text)
            time.sleep(random.randint(1, 3))
        else:
            raise Exception(r.status_code)

    with codecs.open(fp, 'r', 'utf8') as f:
        return f.read()


if __name__ == '__main__':
    import sys
    print download(sys.argv[1])
