#!/usr/bin/env python3.5

import os
import subprocess
import time


ZOPFLI_PATH = os.environ.get("ZOPFLI_PATH", "/usr/bin/zopfli")
I = int(os.environ.get("ZOPFLI_ITERATIONS", 500))


def run(file):
    if os.path.isfile(file + ".gz"):
        print(file + ".gz already existed")
        return 1
    cmd = [ZOPFLI_PATH, "--i{}".format(I), file]
    t0 = time.time()
    exit_code = subprocess.check_call(cmd, timeout=60)
    t1 = time.time()
    if exit_code:
        print(" ".join(cmd))
        print("FAILED TO GENERATE", file + ".gz")
    else:
        print("Created", os.path.basename(file + ".gz"))
        print("Took", "{:.1f}s".format(t1 - t0))
    return 0


if __name__ == "__main__":
    import sys

    for file in sys.argv[1:]:
        run(file)
    sys.exit(0)
