import tempfile

import pytest


@pytest.fixture
def tmpfscacheroot(settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        settings.FSCACHE_ROOT = tmpdir
        yield tmpdir
