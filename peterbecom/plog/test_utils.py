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
        "Please visit https://www2.peterbe.com but don't go to http://www.example.com."
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


def test_linkify_urls_with_ampersands(requestsmock):
    requestsmock.head("https://www.youtobe.com", text="Works", status_code=200)
    text = "link: https://www.youtobe.com/watch?v=2rGuXYAQb8s&feature=share"
    html = utils.render_comment_text(text)
    assert (
        '<a href="https://www.youtobe.com/watch?v=2rGuXYAQb8s&amp;feature=share" '
        'rel="nofollow">https://www.youtobe.com/watch?v=2rGuXYAQb8s&amp;feature=share'
        "</a>"
    ) in html


def test_linkify_urls_with_fragments(requestsmock):
    requestsmock.head("https://www.youtobe.com", text="Works", status_code=200)
    text = "link: https://www.youtobe.com/watch#anchor"
    html = utils.render_comment_text(text)
    assert (
        '<a href="https://www.youtobe.com/watch#anchor" '
        'rel="nofollow">https://www.youtobe.com/watch#anchor'
        "</a>"
    ) in html


def test_linkify_urls_not_http():
    text = """
Email me mailto:mail@example.com
Or call me on tel:123456789
Or you can just go to ftp://archive.example.com
But SSH is better ssh://root@git.example.com
Then open file:///tmp/foo.txt
    """
    html = utils.render_comment_text(text)
    assert '<a href="mailto:mail@example.com">mailto:mail@example.com</a>' in html
    assert " ftp://" in html  # that it does not become a link.
    assert " ssh://" in html  # that it does not become a link.
    assert " file://" in html  # that it does not become a link.


def test_linkify_actual_domain_but_still_bad(requestsmock):
    requestsmock.head("http://sentence.it", text="Works", status_code=200)
    requestsmock.head("http://please.so", text="Works", status_code=200)
    text = "Here is a sentence.It starts with.\n"
    text += "But what about http://please.So it will match!"
    html = utils.render_comment_text(text)
    assert '<a href="http://please.So" rel="nofollow">http://please.So</a>' in html
    assert "a sentence.It starts" in html
