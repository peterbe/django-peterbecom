import subprocess

from django.conf import settings


class ZopfliException(Exception):
    """Happens when the zopfli command fails"""


def zopfli_file(filepath, i=500, timeout=60):
    destination = filepath + ".gz"
    cmd = [settings.ZOPFLI_PATH, "--i{}".format(i), filepath]
    exit_code = subprocess.check_call(cmd, timeout=timeout)
    if exit_code:
        raise ZopfliException("{} on ({})".format(exit_code, " ".join(cmd)))
    return destination
