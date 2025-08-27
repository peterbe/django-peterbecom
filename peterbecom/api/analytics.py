import datetime
import json
import re
import time
from collections import Counter
from functools import wraps

from django import http
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.utils import DataError, ProgrammingError
from sql_metadata import Parser


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
    if request.method == "POST":
        q = json.loads(request.body.decode("utf-8")).get("query")
    else:
        q = request.GET.get("query")

    if not q:
        return http.JsonResponse({"error": "missing 'query'"}, status=400)
    try:
        parsed = Parser(q)
        if parsed.query_type != "SELECT":
            error = f"Only SELECT queries are allowed (not {parsed.query_type})"
            return http.JsonResponse({"error": error}, status=400)

    except ValueError:
        error = f"Query can not be parsed: {q!r}"
        return http.JsonResponse({"error": error}, status=400)

    only_valid = ("base_analyticsevent", "base_analyticsgeoevent", "base_requestlog")
    for table in parsed.tables:
        if table == "analytics_geo":
            q = re.sub(r"\banalytics_geo\b", "base_analyticsgeoevent", q)

        elif table == "analytics":
            q = re.sub(r"\banalytics\b", "base_analyticsevent", q)

        elif table == "analyticsrollupsdaily":
            q = re.sub(r"\banalyticsrollupsdaily\b", "base_analyticsrollupsdaily", q)

        elif table == "requestlog":
            q = re.sub(r"\brequestlog\b", "base_requestlog", q)

        elif table not in only_valid:
            error = f"{table!r} is not a valid table."
            return http.JsonResponse({"error": error}, status=400)

    rows = []
    t0 = time.time()

    count = 0
    MAX_ROWS = 1_000
    maxed_rows = False
    with connection.cursor() as cursor:
        try:
            cursor.execute(q)
        except (ProgrammingError, DataError) as e:
            print("QUERY___________________________________")
            print(q)
            print("ERROR___________________________________")
            print(e)

            error = f"Unable to execute SQL query.\n{e}"
            return http.JsonResponse({"error": error}, status=400)
        columns = [col[0] for col in cursor.description]
        if len(set(columns)) != len(columns):
            # E.g. ['?column?', '?column?']
            # Turn that into ['?column?', '?column? (2)']
            seen = Counter()
            new_columns = []
            for col in columns:
                seen[col] += 1
                if seen[col] > 1:
                    new_columns.append(f"{col} ({seen[col]})")
                else:
                    new_columns.append(col)
            columns = new_columns
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
            count += 1
            if count >= MAX_ROWS:
                maxed_rows = True
                break
    t1 = time.time()
    print(f"[Took: {t1 - t0:.2f} seconds] {q!r}")
    meta = {"took_seconds": t1 - t0, "count_rows": count, "maxed_rows": maxed_rows}
    error = None
    return http.JsonResponse(
        {"rows": rows, "meta": meta, "error": error}, encoder=CustomJSONEncoder
    )


class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.timedelta):
            return str(o)
        return super().default(o)
