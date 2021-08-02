from django import http
from django.urls import path, include
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = staticfiles_urlpatterns()

urlpatterns += [
    path("ajaxornot/", include("peterbecom.ajaxornot.urls", namespace="ajaxornot")),
    path("cdnthis/", include("peterbecom.cdnthis.urls", namespace="cdnthis")),
    path("localvsxhr/", include("peterbecom.localvsxhr.urls", namespace="localvsxhr")),
    path(
        "podcasttime/",
        include("peterbecom.podcasttime.urls", namespace="podcasttime"),
    ),
    path("awspa/", include("peterbecom.awspa.urls", namespace="awspa")),
    path("api/v0/", include("peterbecom.api.urls", namespace="api")),
    path("plog/", include("peterbecom.plog.urls")),
    path("minimalcss/", include("peterbecom.minimalcss.urls")),
    path("chiveproxy", lambda x: http.HttpResponseRedirect("/chiveproxy/")),
    path("chiveproxy/", include("peterbecom.chiveproxy.urls")),
    path("", include("peterbecom.homepage.urls")),
]
