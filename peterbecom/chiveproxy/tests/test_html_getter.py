from peterbecom.chiveproxy.html_getter import suck


def test_happy_path():
    output = suck("https://www.peterbe.com")
    assert output.startswith('<html lang="en">')
