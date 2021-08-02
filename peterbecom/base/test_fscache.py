import os

from django import http
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser

from peterbecom.base import fscache


def test_path_to_fs_path(tmpfscacheroot):
    assert fscache.path_to_fs_path("/foo/bar") == tmpfscacheroot / "foo/bar/index.html"


def test_create_parents(tmpfscacheroot):
    fs_path = fscache.path_to_fs_path("/foo/bar")
    fscache.create_parents(fs_path)
    assert os.path.isdir(os.path.dirname(fs_path))


def test_cache_request():
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    response = http.HttpResponse()
    assert fscache.cache_request(request, response)

    response = http.HttpResponse(status=404)
    assert not fscache.cache_request(request, response)

    request = RequestFactory().get("/", {"foo": "bar"})
    response = http.HttpResponse()
    assert not fscache.cache_request(request, response)

    request = RequestFactory().get("/plog/post/ping")
    request.user = AnonymousUser()
    response = http.HttpResponse()
    assert not fscache.cache_request(request, response)

    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    request._fscache_disable = True
    response = http.HttpResponse()
    assert not fscache.cache_request(request, response)
