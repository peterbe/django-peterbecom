from functools import wraps

from django import http


def api_superuser_required(view_func):
    """Decorator that will return a 403 JSON response if the user
    is *not* a superuser.
    Use this decorator *after* others like api_login_required.
    """

    @wraps(view_func)
    def inner(request, *args, **kwargs):
        if not request.user.is_superuser:
            error_msg = "Must be superuser to access this view."
            # raise PermissionDenied(error_msg)
            return http.JsonResponse({"error": error_msg}, status=403)
        return view_func(request, *args, **kwargs)

    return inner
