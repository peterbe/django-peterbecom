import backoff
import requests

from django import http
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.contrib.auth.signals import user_logged_in
from django.conf import settings


class OIDCEndpointRequestError(Exception):
    """Happens when the server-to-server communication with the OIDC
    endpoint succeeds but the OIDC endpoints responds with a status code
    less than 500 and not equal to 200 or 401."""


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if not response:
            response = self.get_response(request)
        return response

    def process_request(self, request):
        if request.path.startswith("/api/"):
            if request.headers.get("Authorization") or request.method != "GET":
                header_value = request.headers["Authorization"]
                if not header_value:
                    return http.JsonResponse(
                        {"error": "No 'Authorization' header"}, status=403
                    )
                try:
                    access_token = header_value.split("Bearer")[1].strip()
                except IndexError:
                    return http.JsonResponse(
                        {"error": "invalid header value"}, status=403
                    )
                cache_key = f"bearer-to-user-info:{access_token[:12]}"
                user = cache.get(cache_key)
                was_in_cache = user is not None
                if not was_in_cache:
                    user_info = self.fetch_oidc_user_profile(access_token)
                    if isinstance(user_info, http.HttpResponse):
                        cache.delete(cache_key)
                        return user_info
                    if user_info:
                        user_model = get_user_model()
                        try:
                            user = user_model.objects.get(email=user_info["email"])
                            cache.set(cache_key, user, 60 * 60)
                        except user_model.DoesNotExist:
                            return http.JsonResponse(
                                {"error": "Not creating users"}, status=403
                            )
                if not user:
                    return http.JsonResponse(
                        {"error": "access_token invalid"}, status=403
                    )
                request.user = user
                if not was_in_cache:
                    user_logged_in.send(
                        sender=user.__class__, request=request, user=user
                    )

            request.csrf_processing_done = True

    @backoff.on_exception(
        backoff.constant, requests.exceptions.RequestException, max_tries=5
    )
    def fetch_oidc_user_profile(self, access_token):
        url = settings.OIDC_USER_ENDPOINT
        response = requests.get(
            url, headers={"Authorization": "Bearer {}".format(access_token)}
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # The OIDC provider did not like the access token.
            return http.HttpResponseForbidden("Unauthorized access token")
        elif response.status_code >= 500:
            raise requests.exceptions.RequestException(
                f"{response.status_code} on {url}"
            )

        # This could happen if, for some reason, we're not configured to be
        # allowed to talk to the OIDC endpoint.
        raise OIDCEndpointRequestError(response.status_code)
