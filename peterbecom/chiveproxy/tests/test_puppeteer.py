from peterbecom.chiveproxy.puppeteer import suck


def test_happy_path():
    output = suck("https://www.peterbe.com")
    assert output.startswith("<!DOCTYPE html>")
