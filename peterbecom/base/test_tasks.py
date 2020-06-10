from pathlib import Path

import pytest

from peterbecom.base import tasks


@pytest.mark.django_db
def test_post_process_cached_html_happy_path(tmpfscacheroot, requestsmock, settings):
    assert isinstance(tmpfscacheroot, Path), type(tmpfscacheroot)
    requestsmock.post(
        settings.MINIMALCSS_SERVER_URL + "/minimize",
        json={
            "result": {
                "stylesheetContents": {
                    "https://example.com/foo.css": "body { color: blue; }"
                },
                "finalCss": "body{color:blue}h1{font-weight:bold}",
            }
        },
    )
    fn = tmpfscacheroot / "index.html"
    html = """
        <!doctype html>
        <html>
        <head>
        <link rel="stylesheet" href="/foo.css">
        <style>
        h1 { font-weight: bold; }
        </style>
        </head>
        <body>
          <h1 class="header">Header</h1>
        </body>
        </html>
        """.strip()
    with open(fn, "w") as f:
        f.write(html)

    tasks.post_process_cached_html(fn, "http://www.peterbe.example.com/page")

    assert Path(str(fn) + ".original").exists()
    assert Path(str(fn) + ".br").exists()
    assert Path(str(fn) + ".gz").exists()
    with open(fn) as f:
        optimized_html = f.read()

    assert "<h1 class=header>Header</h1>" in optimized_html

    # The smart css warmup and the html minification at work.
    assert "<link rel=stylesheet href=/foo.css media=print" in optimized_html

    assert "body{color:blue}h1{font-weight:bold}</style>" in optimized_html
