import concurrent.futures
import os
import random
import time
from collections import defaultdict

import requests


def _get_size(url):
    sleep = random.random() / 10
    # print("sleep", sleep)
    time.sleep(sleep)
    r = requests.get(url)
    # print(r.status_code)
    if not r.text:
        print(
            "EMPTY TEXT!!",
            "File exists?",
            os.path.isfile(
                "./peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html"
            ),
            "Size?",
            os.stat(
                "./peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html"
            ).st_size,
            "X-Local?",
            repr(r.headers["x-local"]),
        )
    assert len(r.text), r.headers["x-local"]
    return len(r.text), r.headers["x-local"]


def run(url, times=100):
    sizes = []
    futures = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for _ in range(times):
            futures.append(executor.submit(_get_size, url))
        for future in concurrent.futures.as_completed(futures):
            sizes.append(future.result())

    print(sizes)
    if sizes:
        count_x_locals = defaultdict(int)
        for _, x_local in sizes:
            count_x_locals[x_local] += 1
        for key, count in count_x_locals.items():
            print(key, "{:.1f}%".format(100 * count / sum(count_x_locals.values())))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(run(sys.argv[1]))
