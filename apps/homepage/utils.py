import re
from django import http
from django.db.models import Q
from apps.plog.models import Category


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
