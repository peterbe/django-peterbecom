import re

import bleach
from django.db.models import F

from peterbecom.plog.models import SpamCommentPattern, SpamCommentSignature


def increment_pattern(id: int):
    SpamCommentPattern.objects.filter(id=id).update(kills=F("kills") + 1)


def increment_signature(id: int):
    SpamCommentSignature.objects.filter(id=id).update(kills=F("kills") + 1)


def contains_spam_url_patterns(text):
    html = bleach.clean(text)

    problems = []

    qs = SpamCommentPattern.objects.filter(is_url_pattern=True).values("pattern", "id")
    patterns_map = {x["pattern"]: x["id"] for x in qs}
    regex = re.compile(r"|".join([re.escape(x) for x in patterns_map.keys()]))

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

        for found in regex.findall(href):
            problems.append(found)
            increment_pattern(patterns_map[found])

    bleach.linkify(html, callbacks=[scrutinize_link])
    return bool(problems)


def contains_spam_patterns(text):
    qs = SpamCommentPattern.objects.filter(is_url_pattern=False, is_regex=False).values(
        "pattern", "id"
    )
    for pattern in qs:
        if pattern["pattern"] in text:
            increment_pattern(pattern["id"])
            return True
    return False


def is_trash_commenter(name, email):
    for signature in SpamCommentSignature.objects.all().values("id", "name", "email"):
        if signature["name"] is not None and name is not None:
            if signature["name"] == name:
                increment_signature(signature["id"])
                return True

        if signature["email"] is not None and email is not None:
            if signature["email"] == email:
                increment_signature(signature["id"])
                return True

    return False
