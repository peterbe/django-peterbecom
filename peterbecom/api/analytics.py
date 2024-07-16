import time
import re
from functools import wraps

from django.db import connection
from django.db.utils import ProgrammingError
from sql_metadata import Parser
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
            return http.JsonResponse({"error": error_msg}, status=403)
        return view_func(request, *args, **kwargs)

    return inner


@api_superuser_required
def query(request):
    q = request.GET.get("query")
    print("QUERY:", repr(q))
    try:
        parsed = Parser(q)
    except ValueError:
        error = f"Query can not be parsed: {q!r}"
        return http.JsonResponse({"error": error}, status=400)
    if parsed.query_type != "SELECT":
        error = f"Only SELECT queries are allowed (not {parsed.query_type})"
        return http.JsonResponse({"error": error}, status=400)

    for table in parsed.tables:
        if table == "analytics":
            q = re.sub(r"\banalytics\b", "base_analyticsevent", q)

        elif table != "base_analyticsevent":
            error = "Can only select on `base_analyticsevent` or `analytics`"
            return http.JsonResponse({"error": error}, status=400)

    rows = []
    t0 = time.time()

    count = 0
    MAX_ROWS = 1_000
    maxed_rows = False
    with connection.cursor() as cursor:
        try:
            cursor.execute(q)
        except ProgrammingError as e:
            error = f"Unable to execute SQL query.\n{e}"
            return http.JsonResponse({"error": error}, status=400)
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
            count += 1
            if count >= MAX_ROWS:
                maxed_rows = True
                break
    t1 = time.time()
    print(repr(q), "Took:", round(t1 - t0, 2), "seconds")
    meta = {"took_seconds": t1 - t0, "count_rows": count, "maxed_rows": maxed_rows}
    error = None
    return http.JsonResponse({"rows": rows, "meta": meta, "error": error})