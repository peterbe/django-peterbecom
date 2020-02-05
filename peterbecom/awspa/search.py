import time
import json
import os
import tempfile
import functools
import shlex


from amazon.paapi import AmazonAPI, Product
from django.conf import settings


import delegator

from django.conf import settings


def with_tmpdir(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        with tempfile.TemporaryDirectory() as dir_:
            return f(dir_, *args, **kwargs)

    return inner


class SubprocessError(Exception):
    """Happens when the subprocess fails"""


class BadSearchResult(Exception):
    """Happens when the output from the subprocess isn't valid."""


class RateLimitedError(Exception):
    """When the AWS PA API says something like:

        You are submitting requests too quickly.
        Please retry your requests at a slower rate.

    """


class NoProductFoundError(Exception):
    """You do a lookup by an ASIN but nothing comes back"""


def search(keyword, searchindex="All", sleep=0):
    output = _raw_search(keyword=keyword, searchindex=searchindex)
    if sleep > 0:
        time.sleep(sleep)
    items = output["Items"]
    errors = items["Request"].get("Errors")
    if errors:
        return [], errors["Error"]
    products = items["Item"]
    if isinstance(products, dict):
        products = [products]
    return products, None


def product_to_dict(p):
    assert isinstance(p, Product), type(p)
    d = {}
    for key in dir(p):
        if key.startswith("_"):
            continue
        value = getattr(p, key)
        if isinstance(value, Product):
            value = product_to_dict(value)
        d[key] = value
    return d


def lookup(asin, sleep=0):
    amazon = AmazonAPI(
        settings.AWS_PAAPI_ACCESS_KEY,
        settings.AWS_PAAPI_ACCESS_SECRET,
        settings.AWS_ASSOCIATE_TAG,
        "US",
    )
    try:
        product = amazon.get_product(asin)
        if product is None:
            raise NoProductFoundError(asin)
        # XXX How do you get errors??
        return product_to_dict(product), None
    finally:
        if sleep > 0:
            time.sleep(sleep)


@with_tmpdir
def _raw_search(tmpdir, asin=None, keyword=None, searchindex=None):
    with open("/tmp/awspa-searches.log", "a") as f:
        line = "{}\tasin={!r}\tkeyword={!r}\tsearchindex={!r}\n".format(
            int(time.time()), asin, keyword, searchindex
        )
        f.write(line)
        print("AWSPA_SEARCH:", line)
    filename = os.path.join(tmpdir, "out.json")
    cli_path = settings.BASE_DIR / "awspa/cli.js"
    if asin:
        command = "node {} --asin={} --out={}".format(cli_path, asin, filename)
    else:
        assert keyword
        assert searchindex
        command = 'node {} --searchindex={} --out={} "{}"'.format(
            cli_path, searchindex, filename, shlex.quote(keyword)
        )
    # print(command)
    r = delegator.run(command)
    if r.return_code:
        err_out = r.err
        if "You are submitting requests too quickly" in err_out:
            raise RateLimitedError(err_out)
        raise SubprocessError(
            "Return code: {}\tError: {}".format(r.return_code, err_out)
        )
    with open(filename) as f:
        out = f.read()
    try:
        return json.loads(out)
    except json.decoder.JSONDecodeError:
        raise BadSearchResult(out)
