import json
import time

from django.http import HttpResponseForbidden

TRACKBACK_REASON = "Referer checking failed - Referer is insecure while host is secure."


def csrf_failure(request, reason=""):
    if reason == TRACKBACK_REASON and request.path.endswith("/trackback"):
        print("Ignored CSRF reason", repr(reason))
        return HttpResponseForbidden(reason)

    fn = "/tmp/csrf_failure_{}.json".format(int(time.time()))
    with open(fn, "w") as f:
        post_data = {}
        get_data = {}
        if request.method == "POST":
            for key in request.POST:
                post_data[key] = str(request.POST[key])
        else:
            for key in request.GET:
                get_data[key] = str(request.GET[key])
        request_data = {
            "path": request.path,
            "reason": reason,
            "method": request.method,
            "POST": post_data,
            "GET": get_data,
            "headers": dict(request.headers),
            "ip_address": request.META.get("REMOTE_ADDR"),
        }

        json.dump(request_data, f, indent=3)
        print("CSRF FAILURE! Wrote {}".format(fn))
        print(json.dumps(request_data))

    return HttpResponseForbidden(reason)
