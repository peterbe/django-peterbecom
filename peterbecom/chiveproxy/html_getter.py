import time
import os
import signal
import subprocess
from pathlib import Path


class SubprocessError(Exception):
    """Happens when the subprocess fails"""

    def __init__(self, returncode, error, out):
        self.returncode = returncode
        self.error = error
        self.out = out

    def __str__(self):
        return repr(self.error or self.out)


# Adapted from https://stackoverflow.com/a/36955420/205832
def subprocess_execute(command, timeout_seconds=30, shell=True):
    with subprocess.Popen(
        command,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    ) as process:
        try:
            out, err = process.communicate(timeout=timeout_seconds)
            if process.returncode:
                raise SubprocessError(
                    process.returncode,
                    error=err.decode("utf-8"),
                    out=out.decode("utf-8"),
                )
            return out, err
        except subprocess.TimeoutExpired:
            # Without this, I've seen, at least on Mac, that the process can linger.
            # What it does is that it tells all the children to kill. Not just
            # immediate process. Not all executable programs have children of their
            # own, but if they don't this stuff won't fail.
            os.killpg(process.pid, signal.SIGINT)  # send signal to the process group
            raise


def suck(url, attempts=3, debug=False):
    here = Path(__file__).parent
    executable = here / "out" / "html_getter"
    if not executable.exists():
        raise FileNotFoundError(
            f"The executable {executable} does not exist. Did you compile it?"
        )
    command = f'{executable} "{url}"'
    if debug:
        print("Command:", command)

    t0 = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        try:
            output, _ = subprocess_execute(command, timeout_seconds=60)
            break
        except subprocess.TimeoutExpired:
            if attempt >= attempts:
                raise
    if debug:
        t1 = time.monotonic()
        print(f"Took: {t1 - t0:.2f}s to run: {command}")

    return output.decode("utf-8")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    assert args
    url = args[0]
    print(suck(url, debug=True))
