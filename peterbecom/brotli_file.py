from pathlib import Path

import brotli


def brotli_file(filepath: Path):
    assert isinstance(filepath, Path), type(filepath)
    destination = Path(str(filepath) + ".br")
    with open(filepath, "rb") as source, open(destination, "wb") as dest:
        dest.write(brotli.compress(source.read()))

    return destination
