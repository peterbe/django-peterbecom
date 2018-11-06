# from django.core.exceptions import PermissionDenied


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(request.path)
        request.csrf_processing_done = True
        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response
