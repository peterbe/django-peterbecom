import brotli


def brotli_file(filepath):
    destination = filepath + ".br"
    with open(filepath, "rb") as source, open(destination, "wb") as dest:
        dest.write(brotli.compress(source.read()))

    return destination
