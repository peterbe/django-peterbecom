from django import http
from django.urls import path
from django.conf.urls import include, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns


urlpatterns = staticfiles_urlpatterns()

urlpatterns += [
    url(r"^ajaxornot/", include("peterbecom.ajaxornot.urls", namespace="ajaxornot")),
    url(r"^cdnthis$", lambda x: http.HttpResponseRedirect("/cdnthis/")),
    url(r"^cdnthis/", include("peterbecom.cdnthis.urls", namespace="cdnthis")),
    url(r"^localvsxhr$", lambda x: http.HttpResponseRedirect("/localvsxhr/")),
    url(r"^localvsxhr/", include("peterbecom.localvsxhr.urls", namespace="localvsxhr")),
    url(r"^podcasttime$", lambda x: http.HttpResponseRedirect("/podcasttime/")),
    url(
        r"^podcasttime/",
        include("peterbecom.podcasttime.urls", namespace="podcasttime"),
    ),
    url(r"^awspa/", include("peterbecom.awspa.urls", namespace="awspa")),
    url(r"^api/v0/", include("peterbecom.api.urls", namespace="api")),
    url(r"^plog/", include("peterbecom.plog.urls")),
    url(r"^plog$", lambda x: http.HttpResponseRedirect("/plog/")),
    url(r"^minimalcss/", include("peterbecom.minimalcss.urls")),
    path("chiveproxy", lambda x: http.HttpResponseRedirect("/chiveproxy/")),
    path("chiveproxy/", include("peterbecom.chiveproxy.urls")),
    url(r"", include("peterbecom.homepage.urls")),
]
