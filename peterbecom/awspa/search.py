import time
import json

import delegator


class SubprocessError(Exception):
    """Happens when the subprocess fails"""


def search(keyword, searchindex='All', sleep=0):
    output = _raw_search(keyword, searchindex)
    if sleep > 0:
        time.sleep(sleep)
    items = output['Items']
    errors = items['Request'].get('Errors')
    if errors:
        return [], errors['Error']
    return items['Item'], None


def _raw_search(keyword, searchindex):
    r = delegator.run(
        'node awspa/cli.js --searchindex={} "{}"'.format(
            searchindex,
            keyword,
        )
    )
    if r.return_code:
        raise SubprocessError('Return code: {}\tError: {}'.format(
            r.return_code,
            r.err
        ))

    return json.loads(r.out)
