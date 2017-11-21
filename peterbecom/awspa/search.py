import time
import json
import os
import tempfile
import functools
import shlex

import delegator


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


def search(keyword, searchindex='All', sleep=0):
    output = _raw_search(keyword, searchindex)
    if sleep > 0:
        time.sleep(sleep)
    items = output['Items']
    errors = items['Request'].get('Errors')
    if errors:
        return [], errors['Error']
    products = items['Item']
    if isinstance(products, dict):
        products = [products]
    return products, None


@with_tmpdir
def _raw_search(tmpdir, keyword, searchindex):
    filename = os.path.join(tmpdir, 'out.json')
    command = 'node awspa/cli.js --searchindex={} --out={} "{}"'.format(
        searchindex,
        filename,
        shlex.quote(keyword),
    )
    # print(command)
    r = delegator.run(command)
    if r.return_code:
        raise SubprocessError('Return code: {}\tError: {}'.format(
            r.return_code,
            r.err
        ))
    with open(filename) as f:
        out = f.read()
    try:
        return json.loads(out)
    except json.decoder.JSONDecodeError:
        raise BadSearchResult(out)
