import tempfile

import requests_mock
import pytest


@pytest.fixture
def tmpfscacheroot(settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        settings.FSCACHE_ROOT = tmpdir
        yield tmpdir


@pytest.fixture
def requestsmock():
    """Return a context where requests are all mocked.
    Usage::

        def test_something(requestsmock):
            requestsmock.get(
                'https://example.com/path'
                content=b'The content'
            )
            # Do stuff that involves requests.get('http://example.com/path')
    """
    with requests_mock.mock() as m:
        yield m
