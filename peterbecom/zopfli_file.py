from pathlib import Path

from zopfli import gzip as zopfli


def zopfli_file(filepath: Path, i=15):
    assert isinstance(filepath, Path), type(filepath)
    destination = Path(str(filepath) + ".gz")
    with open(filepath) as source, open(destination, "wb") as dest:
        dest.write(zopfli.compress(source.read(), numiterations=i))

    return destination


def benchmark(fp):
    import os
    import shutil
    import time

    orig_size = prev_size = os.stat(fp).st_size
    print("Original size:", orig_size)

    for i in [1, 5, 15, 25, 100, 500]:
        fpi = "/tmp/zopfli_file_benchmark.{}.{}".format(i, os.path.basename(fp))
        shutil.copy(fp, fpi)
        t0 = time.time()
        zopfli_file(fpi, i)
        t1 = time.time()
        new_size = os.stat(fpi + ".gz").st_size
        print(
            str(i).ljust(3),
            "{:.2f}s".format(t1 - t0),
            str(new_size).ljust(10),
            str(prev_size - new_size).ljust(10),
            "{:.1f}%".format(100 * new_size / orig_size),
        )
        prev_size = new_size


if __name__ == "__main__":
    import sys

    benchmark(sys.argv[1])
