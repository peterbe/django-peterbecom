from django import http


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
            if not request.user.is_authenticated:
                if not request.path.startswith("/api/v0/whoami"):
                    return http.HttpResponseForbidden("Not authenticated")
            request.csrf_processing_done = True
