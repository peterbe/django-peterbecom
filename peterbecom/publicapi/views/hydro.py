import random
import time

from django import http
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def receive(request):
    if not settings.DEBUG:
        return http.HttpResponseForbidden("Not enabled in production.")
    if request.method != "POST":
        return http.HttpResponseNotAllowed("most be post")
    # print(request.META.keys())
    # print([x for x in request.META.keys() if "TYPE" in x])
    if not request.META["HTTP_X_HYDRO_APP"]:
        return http.HttpResponseBadRequest("Missing 'X-Hydro-App' header")
    if not request.META["HTTP_AUTHORIZATION"]:
        return http.HttpResponseForbidden("Authorization header")

    if random.random() > 0.9:
        return http.JsonResponse(
            {"message": "9999ms has passed since batch creation", "retriable": 0},
            status=419,
        )
    if random.random() > 0.7:
        return http.JsonResponse(
            {"message": "Sorry", "retriable": 1},
            status=418,
        )
    if random.random() > 0.7:
        return http.JsonResponse({"grumpy": True}, status=418)
    if random.random() > 0.8:
        print("Sleep!!")
        time.sleep(2900 + random.random() * 500)

    return http.JsonResponse({"status": "SUCCESS", "count": 1})
