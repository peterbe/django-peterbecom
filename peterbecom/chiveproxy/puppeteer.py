import os

import delegator


class SubprocessError(Exception):
    """Happens when the subprocess fails"""


def suck(url):
    js_file = os.path.join(os.path.dirname(__file__), "puppeteer_sucks.js")
    command = 'node {} "{}"'.format(js_file, url)
    r = delegator.run(command)
    if r.return_code:
        err_out = r.err
        raise SubprocessError(
            "Return code: {}\tError: {}".format(r.return_code, err_out)
        )
    html = r.out

    return html


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    assert args
    url = args[0]
    print(suck(url))
