import backoff
import requests

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.core.exceptions import PermissionDenied


class OIDCEndpointRequestError(Exception):
    """Happens when the server-to-server communication with the OIDC
    endpoint succeeds but the OIDC endpoints responds with a status code
    less than 500 and not equal to 200 or 401."""


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            if request.method != "GET":
                header_value = request.META.get("HTTP_AUTHORIZATION")
                if not header_value:
                    raise PermissionDenied("No HTTP_AUTHORIZATION")
                access_token = header_value.split("Bearer")[1].strip()
                cache_key = "bearer-to-user-info"
                user_info = cache.get(cache_key)
                if user_info is None:
                    user_info = self.fetch_oidc_user_profile(access_token)
                    cache.set(cache_key, user_info, 60 * 60)
                if user_info:
                    request.user = get_user_model().objects.get(
                        email=user_info["email"]
                    )

            request.csrf_processing_done = True

        return self.get_response(request)

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
            raise PermissionDenied("Unauthorized access token")
        elif response.status_code >= 500:
            raise requests.exceptions.RequestException(
                "{} on {}".format(response.status_code, url)
            )

        # This could happen if, for some reason, we're not configured to be
        # allowed to talk to the OIDC endpoint.
        raise OIDCEndpointRequestError(response.status_code)
