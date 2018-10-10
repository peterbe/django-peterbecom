from requests.exceptions import ConnectionError

from peterbecom.plog import utils


def test_render_comment_text_with_leading_whitespace():
    text = """Check out my function:

def foo():
    if 1 == 2:
        return 3

    """.strip()
    html = utils.render_comment_text(text)
    assert "<br>&nbsp;&nbsp;&nbsp;&nbsp;if 1 == 2:" in html


def test_render_comment_text_with_xss():
    text = """
        Come check out my <textarea>
    """.strip()
    html = utils.render_comment_text(text)
    assert "<textarea>" not in html
    assert "&lt;textarea&gt;" in html


def test_render_comment_text_with_xss2():
    text = """
        Come check out my < textarea >
    """.strip()
    html = utils.render_comment_text(text)
    assert "< textarea >" not in html
    assert "&lt; textarea &gt;" in html


def test_linkify_special_domains(settings, requestsmock):
    requestsmock.head("http://www.example.com", text="Welcome!", status_code=200)
    settings.NOFOLLOW_EXCEPTIONS = ["www2.peterbe.com"]
    text = (
        "Please visit https://www2.peterbe.com but "
        "don't go to http://www.example.com."
    )
    html = utils.render_comment_text(text)
    assert (
        '<a href="http://www.example.com" rel="nofollow">http://www.example.com</a>'
    ) in html
    assert '<a href="https://www2.peterbe.com">https://www2.peterbe.com</a>' in html


def test_linkify_only_valid_domains(requestsmock):

    requestsmock.head("http://foo.at", exc=ConnectionError)

    requestsmock.head(
        "http://google.com",
        text="Redirecting",
        status_code=301,
        headers={"Location": "https://www.google.com"},
    )

    requestsmock.head(
        "http://github.com",
        text="Redirecting",
        status_code=301,
        headers={"Location": "https://github.com"},
    )

    text = """
Please visit foo.at the very least but
don't go to but you can google.com it.
But try github.com too.
    """.strip()
    html = utils.render_comment_text(text)
    assert " foo.at " in html
    assert '<a href="https://foo.at" rel="nofollow">foo.at</a>' not in html
    # Note, didn't dare to change to https:// on this one because the redirect
    # changes domain as well.
    assert '<a href="http://google.com" rel="nofollow">google.com</a>' in html
    # Did dare with this one.
    assert '<a href="https://github.com" rel="nofollow">github.com</a>' in html
