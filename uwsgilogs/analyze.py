import re
from collections import defaultdict

uri_reg = re.compile('(GET|HEAD) (.*?) ')
size_time_reg = re.compile('generated (\d+) bytes in (\d+) msecs')


def analyze(filepath):
    times = defaultdict(list)
    sizes = defaultdict(list)

    with open(filepath) as f:
        for line in f:
            if 'HTTP/1.1 200' not in line:
                continue
            try:
                method, uri, = uri_reg.findall(line)[0]
                size, time = [int(x) for x in size_time_reg.findall(line)[0]]
            except (ValueError, IndexError):
                continue
            # print repr(line)
            # print (uri, size, time)
            times[uri].append(time)
            sizes[uri].append(size)

    show(sizes, 'SIZES', 'bytes')
    show(times, 'TIMES', 'msecs')


def show(stuff, label, unit):
    print label
    processed = {}
    for k, values in stuff.items():
        processed[k] = {
            'tim': len(values),
            'sum': 1.0 * sum(values),
            'avg': 1.0 * sum(values) / len(values),
            'med': 1.0 * sorted(values)[len(values)/2],
        }

    sorted_ = sorted(
        processed.items(),
        key=lambda x: x[1]['sum'],
        reverse=True
    )
    for uri, data in sorted_[:10]:
        print "\t", uri
        print "\t\t#  : %d %s" % (data['tim'], 'times')
        print "\t\tsum: %.1f %s" % (data['sum'], unit)
        print "\t\tavg: %.1f %s" % (data['avg'], unit)
        print "\t\tmed: %.1f %s" % (data['med'], unit)
        print

if __name__ == '__main__':
    import sys
    f = sys.argv[1:][0]
    analyze(f)
