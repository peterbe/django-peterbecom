import os

import pytest

from peterbecom.base import tasks


@pytest.mark.django_db
def test_post_process_cached_html_happy_path(tmpfscacheroot, requestsmock, settings):
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


# @pytest.mark.django_db
# def test_post_process_cached_html_mincss_cached(tmpfscacheroot,
# requestsmock, settings):

#     calls = []

#     def json_callback(request, context):
#         if len(calls) > 1:
#             raise AssertionError(
#                 "mincss POST mock should only be called twice in total"
#             )

#         calls.append(request)
#         return {
#             "result": {
#                 "stylesheetContents": {"foo.css": "body { color: blue; }"},
#                 "finalCss": "body{color:blue}h1{font-weight:bold}",
#             }
#         }

#     requestsmock.post(settings.MINIMALCSS_SERVER_URL + "/minimize",
# json=json_callback)
#     fn = os.path.join(tmpfscacheroot, "index.html")
#     html = """
#         <!doctype html>
#         <html>
#         <head>
#         <link rel="stylesheet" href="/foo.css">
#         <style>
#         h1 { font-weight: bold; }
#         </style>
#         </head>
#         <body>
#           <h1 class="header">Header</h1>
#         </body>
#         <!-- FSCache 111 -->
#         </html>
#         """.strip()
#     with open(fn, "w") as f:
#         f.write(html)

#     original_ts = os.stat(fn).st_mtime

#     tasks.post_process_cached_html(fn, "http://www.peterbe.example.com/page")

#     assert os.path.isfile(fn)
#     with open(fn) as f:
#         optimized_html = f.read()
#     assert os.path.isfile(fn + ".original")
#     assert os.path.isfile(fn + ".br")
#     assert os.path.isfile(fn + ".gz")

#     # Rewrite it with the same HTML!
#     with open(fn, "w") as f:
#         f.write(html)

#     # Now run it again and the cache file should get used.
#     tasks.post_process_cached_html(fn, "http://www.peterbe.example.com/page")
#     second_ts = os.stat(fn).st_mtime
#     assert original_ts != second_ts
#     with open(fn) as f:
#         optimized_html_again = f.read()
#     assert optimized_html == optimized_html_again

#     # Rewrite it again but a slightly different FSCache HTML comment
#     with open(fn, "w") as f:
#         f.write(html.replace("FSCache 111", "FSCache 222"))

#     # Now run it again and the cache file should get used.
#     tasks.post_process_cached_html(fn, "http://www.peterbe.example.com/page")
#     second_ts = os.stat(fn).st_mtime
#     assert original_ts != second_ts
#     with open(fn) as f:
#         optimized_html_again = f.read()
#     assert optimized_html == optimized_html_again

#     # OK, this time, make the HTML slightly different.
#     with open(fn, "w") as f:
#         f.write(html.replace("Header", "Different Headline"))
#     tasks.post_process_cached_html(fn, "http://www.peterbe.example.com/page")
#     second_ts = os.stat(fn).st_mtime
#     assert original_ts != second_ts
#     with open(fn) as f:
#         optimized_html_again = f.read()
#     assert optimized_html != optimized_html_again
