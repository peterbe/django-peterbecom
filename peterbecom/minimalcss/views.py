from django import http
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def minimize(request):
    return http.HttpResponse("Service discontinued")
