from urllib.parse import urlencode

from django.conf import settings
from django import forms
from django.views.decorators.cache import cache_page
from django.core.exceptions import ImproperlyConfigured
from django import http
from peterbecom.base.utils import requests_retry_session

if not settings.LYRICS_REMOTE:
    raise ImproperlyConfigured("LYRICS_REMOTE not set in settings")


@cache_page(settings.DEBUG and 10 or 60 * 60, key_prefix="publicapi_cache_page")
def search(request):
    form = LyricsSearchForm(request.GET)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    q = form.cleaned_data["q"]
    page = form.cleaned_data.get("page") or 1
    # desperate = form.cleaned_data.get("desperate") or False

    sp = {"q": q}
    if page != 1:
        sp["page"] = page
    # if desperate:
    #     sp["desperate"] = "true"

    remote_url = f"{settings.LYRICS_REMOTE}/api/search?{urlencode(sp)}"
    response = requests_retry_session().get(remote_url)
    print((remote_url, response.status_code))
    if response.status_code != 200:
        if response.status_code == 400:
            return http.JsonResponse(response.json(), status=response.status_code)
        return http.JsonResponse(
            {"error": "Unexpected proxy response code"}, status=response.status_code
        )

    results = []
    metadata = {}

    res = response.json()

    metadata["limit"] = res.get("limit")
    metadata["desperate"] = bool(res.get("desperate"))
    metadata["total"] = res.get("total")
    metadata["search"] = res.get("search")
    for result in res["results"]:

        image = result.get("image")
        if image:
            for key in (
                "url",
                "thumbnail100",
            ):
                if image.get(key):
                    if "None" in image[key]:
                        print("image[key]", image[key])
                    if not image[key].startswith("http"):
                        image[key] = f"{settings.LYRICS_REMOTE}/{image[key]}"

        albums = []
        for album in result.get("albums", []):
            albums.append(
                {
                    "name": album["name"],
                    "year": album.get("year"),
                }
            )
        result["albums"] = albums
        result["artist"] = {"name": result["artist"]["name"]}
        results.append(result)

    context = {"results": results, "metadata": metadata}

    return http.JsonResponse(context)


class LyricsSearchForm(forms.Form):
    q = forms.CharField(max_length=80)
    page = forms.IntegerField(required=False)
    desperate = forms.BooleanField(required=False)

    def clean_q(self):
        value = self.cleaned_data["q"].strip()
        if len(value) < 3:
            raise forms.ValidationError("Query too short")
        return value

    def clean_page(self):
        value = self.cleaned_data["page"]
        if value and value < 1:
            raise forms.ValidationError("Page must be 1 or higher")
        return value


@cache_page(settings.DEBUG and 10 or 60 * 60, key_prefix="publicapi_cache_page")
def song(request):
    form = LyricsSongForm(request.GET)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    id = form.cleaned_data["id"]
    remote_url = f"{settings.LYRICS_REMOTE}/api/song/{id}"
    response = requests_retry_session().get(remote_url)
    if response.status_code != 200:
        return http.JsonResponse(
            {"error": "Unexpected proxy response code"}, status=response.status_code
        )

    res = response.json()
    song_data = res["song"]

    image = song_data.get("image")
    if image:
        for key in (
            "url",
            "thumbnail100",
        ):
            if image.get(key):
                if "None" in image[key]:
                    print("image[key]", image[key])
                if not image[key].startswith("http"):
                    image[key] = f"{settings.LYRICS_REMOTE}/{image[key]}"

    song = {
        "image": image,
        "artist": {
            "name": song_data["artist"]["name"],
        },
        "albums": [
            {
                "name": album["name"],
                "year": album.get("year"),
            }
            for album in song_data.get("albums") or []
        ],
        "name": song_data["name"],
        "text_html": song_data["text_html"],
        "year": song_data.get("year"),
    }

    context = {
        "song": song,
    }
    return http.JsonResponse(context)


class LyricsSongForm(forms.Form):
    id = forms.CharField(max_length=12)

    def clean_id(self):
        value = self.cleaned_data["id"].strip()
        try:
            value = int(value)
            if value < 1:
                raise ValueError("too little")
        except ValueError:
            raise forms.ValidationError("ID not valid")
        return value
