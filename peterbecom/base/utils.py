import json
import random
import traceback
from ipaddress import IPv4Address
from pathlib import Path

import requests
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django_redis import get_redis_connection
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class PathJSONEncoder(DjangoJSONEncoder):
    """Like Django's DjangoJSONEncoder but support of Path objects."""

    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


def get_base_url(request):
    base_url = ["http"]
    if request.is_secure():
        base_url.append("s")
    base_url.append("://")
    x_forwarded_host = request.headers.get("X-Forwarded-Host")
    if x_forwarded_host and x_forwarded_host in settings.ALLOWED_HOSTS:
        base_url.append(x_forwarded_host)
    else:
        base_url.append(request.get_host())
    combined = "".join(base_url)

    if x_forwarded_host == "www.peterbe.com":
        # Exception! When a request comes into https://www.peterbe.com it first
        # goes to the CDN, then to https://www-origin.peterbe.com which is Nginx
        # that terminates the HTTPS and sends it to Node (server.mjs).
        # Then that Node will proxy it forward to the Django backend. At this
        # point the X-Forwarded-Host header is passed along, but the HTTPS is gone.
        # So exclusively for this specific backend, we override and force
        # it "back" to https://.
        combined = combined.replace("http://", "https://")

    return combined


def requests_retry_session(
    retries=4, backoff_factor=0.4, status_forcelist=(500, 502, 504), session=None
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
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def send_pulse_message(msg, raise_errors=False):
    if not settings.SEND_PULSE_MESSAGES:
        return
    try:
        client = get_redis_connection("default")
        if not isinstance(msg, str):
            try:
                msg = json.dumps(msg, cls=PathJSONEncoder)
            except TypeError:
                print(f"Unable to JSON dump msg: {msg!r}")
                raise
        client.publish("pulse", msg)
    except Exception:
        print("EXCEPTION SENDING PUBLISHING PULSE MESSAGE!")
        traceback.print_exc()


def fake_ip_address(seed):
    random.seed(seed)
    # https://codereview.stackexchange.com/a/200348
    return str(IPv4Address(random.getrandbits(32)))


def do_healthcheck():
    from django.core.cache import cache

    from peterbecom.plog.models import BlogItem

    cache.set("foo", "bar", 1)
    assert cache.get("foo") == "bar", "cache not working"
    assert BlogItem.objects.all().count(), "Unable to count BlogItem objects"


def generate_search_terms(title, max_words=4):
    # import nltk
    # nltk.download("stopwords")
    # nltk.download("punkt")

    # Tokenize the title into words
    words = word_tokenize(title)

    # Remove stopwords (common words that may not be informative)
    stop_words = set(stopwords.words("english"))
    filtered_words = [
        word.lower()
        for word in words
        if word.isalnum() and word.lower() not in stop_words
    ]

    # Generate search terms by combining words
    for i in range(len(filtered_words)):
        for j in range(i + 1, len(filtered_words) + 1):
            term = " ".join(filtered_words[i:j])
            if term.isdigit():
                continue
            if j - i == max_words + 1:
                break
            yield term
