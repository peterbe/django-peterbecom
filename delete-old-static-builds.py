import datetime
import os
import re
import time
from collections import defaultdict


def run(*directories):
    for directory in directories:
        _clean(directory)


def _clean(directory):
    now = time.time()
    chksum = re.compile(r"\.[a-f0-9]+\.")

    OLD = datetime.timedelta(days=100)

    def fmt_ts(ts):
        return str(age(ts))

    def age(ts):
        return datetime.timedelta(seconds=int(now - ts))

    to_delete = []

    def delete(fn):
        to_delete.append((os.stat(fn).st_size, fn))

    all_files = defaultdict(list)
    # unique =set()
    for root, _, files in os.walk(os.path.abspath(directory)):
        for file in files:
            fn = os.path.join(root, file)
            simplified = chksum.sub(".*.", fn)
            if fn == simplified:
                continue
            ts = os.stat(fn).st_ctime
            all_files[simplified].append((ts, fn))
            # if fn in unique:
            #     raise Exception
            # unique.add(fn)

    for name, group in all_files.items():
        if len(group) <= 1:
            continue
        group.sort(reverse=True)
        ancient = []
        not_ancient = []
        names = [x[1] for x in group]
        assert len(names) == len(set(names)), names
        for ts, fn in group:
            # print(fmt_ts(ts), fn)
            if age(ts) > OLD:
                ancient.append((ts, fn))
            else:
                not_ancient.append((ts, fn))

        if ancient and not_ancient:
            print("GROUP:", name)
            for ts, fn in ancient:
                print("ANCIENT", fmt_ts(ts), fn)
                delete(fn)
            print(len(not_ancient), "NOT ancient")
            print()

    deleted = [x[0] for x in to_delete]
    names = [x[1] for x in to_delete]
    assert len(names) == len(set(names)), (len(names), len(set(names)))
    for size, fn in to_delete:
        print("del", fn, "{:.1f}K".format(size / 1024))
        os.remove(fn)
    print(
        "DELETED {:,} FILES. SAVED {:.1f}KB".format(len(deleted), sum(deleted) / 1024)
    )


if __name__ == "__main__":
    import sys

    sys.exit(run(*sys.argv[1:]))
