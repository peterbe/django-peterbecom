import re

import bleach
from django.conf import settings

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
        try:
            href = attrs[href_key]
        except KeyError:
            # If the <a> tag doesn't have a 'href', it's definitely bad.
            problems.append("no href attribute")
            return

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


def is_trash_commenter(**params):
    def match(pattern, value):
        if hasattr(pattern, "search"):
            # It's a regex!
            return bool(pattern.search(value))
        return value == pattern

    for combo in settings.TRASH_COMMENT_COMBINATIONS:
        assert combo
        assert None not in combo.values()

        # We can only check on things that are in params.
        common_keys = set(combo) & set([k for k, v in params.items() if v is not None])
        if common_keys and all(match(combo[k], params[k]) for k in common_keys):
            return True

    return False
