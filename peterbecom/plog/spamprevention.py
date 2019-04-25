import re

import bleach
from django.conf import settings


def contains_spam_url_patterns(text):
    assert settings.SPAM_URL_PATTERNS, "Don't use it without some patterns"

    html = bleach.clean(text)

    problems = []

    regex = re.compile(r"|".join([re.escape(x) for x in settings.SPAM_URL_PATTERNS]))

    def scrutinize_link(attrs, new, **kwargs):
        href_key = (None, "href")
        href = attrs[href_key]
        if href.startswith("mailto:") or href.startswith("tel:"):
            # Leave untouched
            return
        if not (href.startswith("http:") or href.startswith("https:")):
            # Bail if it's not a HTTP URL, such as ssh:// or ftp://
            return

        found = regex.findall(href)
        if found:
            problems.append(found)

    bleach.linkify(html, callbacks=[scrutinize_link])
    return bool(problems)
