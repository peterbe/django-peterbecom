import datetime
import re
from django import http
from django.db.models import Q
from peterbecom.apps.plog.models import Category


def split_search(q, keywords):
    params = {}
    s = []
    if re.findall('[^\w]', ''.join(keywords)):
        raise ValueError("keywords can not contain non \w characters")

    regex = re.compile(r'\b(%s):' % '|'.join(keywords), re.I)
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
                params[bit.lower()] = bits[i+1].strip()
                skip_next = True
            elif bit.strip():
                s.append(bit.strip())

    return ' '.join(s), params


def parse_ocs_to_categories(oc):
    ocs = [x.strip().replace('/', '').replace('+',' ')
           for x
           in re.split('oc-(.*?)', oc) if x.strip()]
    categories = Category.objects.filter(name__in=ocs)
    if len(categories) != len(ocs):
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
