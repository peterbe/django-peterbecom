import re

import bleach

from peterbecom.plog.models import SpamCommentPattern


def contains_spam_url_patterns(text):

    html = bleach.clean(text)

    problems = []

    qs = SpamCommentPattern.objects.filter(is_url_pattern=True).values_list(
        "pattern", flat=True
    )
    regex = re.compile(r"|".join([re.escape(x) for x in qs]))

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


def contains_spam_patterns(text):
    qs = SpamCommentPattern.objects.filter(
        is_url_pattern=False, is_regex=False
    ).values_list("pattern", flat=True)
    for pattern in qs:
        if pattern in text:
            return True
    return False
