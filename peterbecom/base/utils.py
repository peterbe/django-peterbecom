from django.conf import settings


def get_base_url(request):
    base_url = ['http']
    if request.is_secure():
        base_url.append('s')
    base_url.append('://')
    x_forwarded_host = request.headers.get("X-Forwarded-Host")
    if x_forwarded_host and x_forwarded_host in settings.ALLOWED_HOSTS:
        base_url.append(x_forwarded_host)
    else:
        base_url.append(request.get_host())
    return ''.join(base_url)
