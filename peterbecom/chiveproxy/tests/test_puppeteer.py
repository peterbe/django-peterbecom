import pytest

from peterbecom.chiveproxy.puppeteer import suck


# These don't work locally and at the moment I just don't care enough to fix
@pytest.mark.skip
def test_happy_path():
    output = suck("https://www.peterbe.com")
    assert output.startswith("<!DOCTYPE html>")
