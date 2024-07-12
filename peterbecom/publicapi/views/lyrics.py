import random
import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django import http
from ..forms import LyricsSearchForm
from peterbecom.base.utils import requests_retry_session

# from django.views.decorators.csrf import csrf_exempt
if not settings.LYRICS_REMOTE:
    raise ImproperlyConfigured("LYRICS_REMOTE not set in settings")


def search(request):
    form = LyricsSearchForm(request.GET)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    q = form.cleaned_data["q"]
    page = form.cleaned_data.get("page") or 1

    sp = {"q": q}
    if page != 1:
        sp["page"] = page

    remote_url = f"{settings.LYRICS_REMOTE}/api/search?{urlencode(sp)}"
    response = requests_retry_session().get(remote_url)
    # print(form.cleaned_data)
    results = []
    metadata = {}
    from pprint import pprint

    res = response.json()
    pprint(res)
    pprint(res["results"][0])
    metadata["limit"] = res.get("limit")
    metadata["desperate"] = bool(res.get("desperate"))
    metadata["total"] = res.get("total")
    metadata["search"] = res.get("search")
    for result in res["results"]:

        # for album in result.get("albums", []):
        #     t100 = album.get("thumbnail100")
        #     if t100 and not (t100.startswith("http")):
        #         if t100.startswith("/"):
        #             t100 = t100[1:]
        #         album["thumbnail100"] = f"{settings.LYRICS_REMOTE}/{t100}"
        #     # album["url"] = f"/album/{album['id']}"

        # artist = result["artist"]
        # t100 = artist.get("thumbnail100")
        # if t100 and not (t100.startswith("http")):
        #     if t100.startswith("/"):
        #         t100 = t100[1:]
        #     artist["thumbnail100"] = f"{settings.LYRICS_REMOTE}/{t100}"
        # # album["url"] = f"/album/{album['id']}"
        image = result.get("image")
        if image:
            for key in (
                "url",
                "thumbnail100",
            ):
                if key in image:
                    if not image[key].startswith("http"):
                        image[key] = f"{settings.LYRICS_REMOTE}/{image[key]}"

        results.append(result)

    # if not settings.DEBUG:
    #     return http.HttpResponseForbidden("Not enabled in production.")
    # if request.method != "POST":
    #     return http.HttpResponseNotAllowed("most be post")
    # # print(request.META.keys())
    # # print([x for x in request.META.keys() if "TYPE" in x])
    # if not request.META["HTTP_X_HYDRO_APP"]:
    #     return http.HttpResponseBadRequest("Missing 'X-Hydro-App' header")
    # if not request.META["HTTP_AUTHORIZATION"]:
    #     return http.HttpResponseForbidden("Authorization header")

    # if random.random() > 0.9:
    #     return http.JsonResponse(
    #         {"message": "9999ms has passed since batch creation", "retriable": 0},
    #         status=419,
    #     )
    # if random.random() > 0.7:
    #     return http.JsonResponse(
    #         {"message": "Sorry", "retriable": 1},
    #         status=418,
    #     )
    # if random.random() > 0.7:
    #     return http.JsonResponse({"grumpy": True}, status=418)
    # if random.random() > 0.8:
    #     print("Sleep!!")
    #     time.sleep(2900 + random.random() * 500)
    # results = []
    # metadata = {}
    context = {"results": results, "metadata": metadata}

    return http.JsonResponse(context)
