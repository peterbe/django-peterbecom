import time
from json.decoder import JSONDecodeError
from urllib.parse import urlencode

from django import forms, http
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.views.decorators.cache import cache_page, never_cache

from peterbecom.base.geo import ip_to_country_code
from peterbecom.base.utils import fake_ip_address, requests_retry_session
from peterbecom.publicapi.views.lyrics_utils import (
    NonJSONError,
    NotOKError,
    RedirectNeeded,
    get_song,
)

if not settings.LYRICS_REMOTE:
    raise ImproperlyConfigured("LYRICS_REMOTE not set in settings")


@cache_page(settings.DEBUG and 10 or 60 * 60, key_prefix="publicapi_cache_page")
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
    response = requests_retry_session(retries=2).get(remote_url)
    if response.status_code != 200:
        if response.status_code == 400:
            try:
                return http.JsonResponse(response.json(), status=response.status_code)
            except JSONDecodeError:
                print(
                    "JSONDECODERROR",
                    {"remote_url": remote_url, "response.text": response.text},
                )
                return http.JsonResponse(
                    {"error": response.text}, status=response.status_code
                )
        return http.JsonResponse(
            {
                "error": f"Unexpected proxy response code ({response.status_code}) on {remote_url}"
            },
            status=response.status_code,
        )

    results = []
    metadata = {}

    try:
        res = response.json()
    except JSONDecodeError:
        print(f"WARNING: JSONDecodeError ({remote_url})", response.text)
        return http.JsonResponse(
            {"error": "Unexpected non-JSON error on fetching search"},
            status=response.status_code,
        )

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

    print("TOP 3 results:", [x["id"] for x in results[:3]])

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


# Lower case TTL because the underlying get_song has a long TTL cache
@cache_page(settings.DEBUG and 10 or 60 * 60, key_prefix="publicapi_cache_page")
def song(request):
    form = LyricsSongForm(request.GET)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    id = form.cleaned_data["id"]

    try:
        res = get_song(id)
    except RedirectNeeded as e:
        return redirect(e.args[0])
    except NotOKError as e:
        return http.JsonResponse(
            {"error": "Unexpected proxy response code"}, status=e.args[0]
        )
    except NonJSONError:
        return http.JsonResponse(
            {"error": "Unexpected non-JSON error on fetching song"},
            status=500,
        )

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


@never_cache
def feature_flag(request):
    if request.GET.get("force"):
        response = http.JsonResponse({"enabled": True})
        response.set_cookie(
            "local-lyrics-server",
            "true",
            max_age=60 * 60 * 24 * 7,
            httponly=True,
        )
        return response
    value = request.COOKIES.get("local-lyrics-server")
    if value is not None:
        return http.JsonResponse({"enabled": value == "true"})

    if value is None:
        ip_addresses = (
            request.headers.get("x-forwarded-for")
            or request.META.get("REMOTE_ADDR")
            or ""
        )
        # X-Forwarded-For might be a comma separated list of IP addresses
        # coming from the CDN. The first is the client.
        # https://www.keycdn.com/blog/x-forwarded-for-cdn
        ip_address = [x.strip() for x in ip_addresses.split(",") if x.strip()][0]
        if (
            ip_address == "127.0.0.1"
            and settings.DEBUG
            and request.get_host().endswith("127.0.0.1:8000")
        ):
            ip_address = fake_ip_address(str(time.time()))

        if ip_address and ip_address != "127.0.0.1":
            # Used by pytest
            if ip_address == "US.US.US.US":
                country_code = "US"
            else:
                country_code = ip_to_country_code(ip_address)
            enabled = False
            if country_code in ["US", "GB", "CA", "DE", "PH", "FR", "IN"]:
                enabled = True

            response = http.JsonResponse({"enabled": enabled})
            response.set_cookie(
                "local-lyrics-server",
                enabled and "true" or "false",
                max_age=enabled and 60 * 60 * 24 * 7 or 60 * 60 * 24,
                httponly=True,
            )
            return response

    return http.JsonResponse({"enabled": False})
