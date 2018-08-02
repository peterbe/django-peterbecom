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
    minified = proc.communicate(input=html.encode("utf-8"))[0].decode("utf-8")
    return minified
