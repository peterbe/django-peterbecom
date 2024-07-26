import re

from django import http
from django.db.models import Q

from peterbecom.plog.models import Category

STOPWORDS = (
    "a able about across after all almost also am among an and "
    "any are as at be because been but by can cannot could dear "
    "did do does either else ever every for from get got had has "
    "have he her hers him his how however i if in into is it its "
    "just least let like likely may me might most must my "
    "neither no nor not of off often on only or other our own "
    "rather said say says she should since so some than that the "
    "their them then there these they this tis to too twas us "
    "wants was we were what when where which while who whom why "
    "will with would yet you your"
)
STOPWORDS_TUPLE = tuple(STOPWORDS.split())


def split_search(q, keywords):
    params = {}
    s = []
    if re.findall(r"[^\w]", "".join(keywords)):
        raise ValueError("keywords can not contain non \\w characters")

    regex = re.compile(r"\b(%s):" % "|".join(keywords), re.I)
    bits = regex.split(q)
    if len(bits) == 1:
        # there was no keyword at all
        return q, {}

    skip_next = False
    for i, bit in enumerate(bits):
        if skip_next:
            skip_next = False
        else:
            if bit in keywords:
                params[bit.lower()] = bits[i + 1].strip()
                skip_next = True
            elif bit.strip():
                s.append(bit.strip())

    return " ".join(s), params


def parse_ocs_to_categories(oc, strict_matching=False):
    oc = re.sub(r"/p\d+$", "", oc)
    ocs = [
        x.strip().replace("/", "").replace("+", " ")
        for x in re.split(r"oc-(.*?)", oc)
        if x.strip()
    ]
    categories = Category.objects.filter(name__in=ocs)
    if strict_matching and len(categories) != len(ocs):
        raise http.Http404("Unrecognized categories")

    return categories


def make_categories_q(categories):
    cat_q = None
    for category in categories:
        if cat_q is None:
            cat_q = Q(categories=category)
        else:
            cat_q = cat_q | Q(categories=category)
    return cat_q
