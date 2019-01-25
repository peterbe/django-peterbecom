import subprocess

from django.conf import settings


def minify_html(html):
    proc = subprocess.Popen(
        [
            settings.HTML_MINIFIER_PATH,
            "--max-line-length",
            "1000",
            "--collapse-whitespace",
            "--remove-comments",
            "--remove-attribute-quotes",
            "--collapse-boolean-attributes",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    html = html.replace("<pre>", "<pre><!-- htmlmin:ignore -->")
    html = html.replace("</pre>", "<!-- htmlmin:ignore --></pre>")
    try:
        minified = proc.communicate(
            input=html.encode("utf-8"), timeout=settings.HTML_MINIFIER_TIMEOUT_SECONDS
        )[0].decode("utf-8")
    except subprocess.TimeoutExpired:
        print("WARNING! HTML minifying took too long.")
        return None
    return minified
