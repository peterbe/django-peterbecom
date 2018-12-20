import os

import pytest

from peterbecom.base import tasks


@pytest.mark.django_db
def test_post_process_cached_html_happy_path(tmpfscacheroot, requestsmock, settings):
    print(settings.MINIMALCSS_SERVER_URL + "/minimize")
    requestsmock.post(
        settings.MINIMALCSS_SERVER_URL + "/minimize",
        json={
            "result": {
                "stylesheetContents": {"foo.css": "body { color: blue; }"},
                "finalCss": "body{color:blue}h1{font-weight:bold}",
            }
        },
    )
    fn = os.path.join(tmpfscacheroot, "index.html")
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

    assert os.path.isfile(fn + ".original")
    assert os.path.isfile(fn + ".br")
    assert os.path.isfile(fn + ".gz")
    with open(fn) as f:
        optimized_html = f.read()

    assert "<h1 class=header>Header</h1>" in optimized_html

    assert "body{color:blue}h1{font-weight:bold}</style>" in optimized_html
