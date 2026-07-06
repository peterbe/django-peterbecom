from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.shortcuts import redirect

from peterbecom.base.utils import get_base_url


def disallow_querystrings(except_keys=()):
    """
    Decorator that redirects to the same URL but without the query strings.
    You can make exceptions, e.g. @disallow_querystrings(except_keys=("foo",))
    which will redirect `/bar?foo=1&baz=2` to `/bar?foo=1`.
    """
    if isinstance(except_keys, str):
        except_keys = (except_keys,)

    def decorator(view_func):
        @wraps(view_func)
        def inner(request, *args, **kwargs):
            if request.GET:
                not_allowed = set(request.GET.keys()) - set(except_keys)
                if not_allowed:
                    # Don't use `request.build_absolute_uri()` because it might
                    # not know the server is behind a CDN.
                    base_url = get_base_url(request)
                    url_parts = urlsplit(base_url + request.get_full_path())
                    query_pairs = parse_qsl(url_parts.query, keep_blank_values=True)
                    query_dict = dict(query_pairs)
                    for key in not_allowed:
                        query_dict.pop(key)
                    new_query_str = urlencode(query_dict)
                    modified_url_parts = url_parts._replace(query=new_query_str)
                    return redirect(modified_url_parts.geturl())

            return view_func(request, *args, **kwargs)

        return inner

    return decorator
