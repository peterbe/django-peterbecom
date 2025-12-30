import mock
import pytest
import requests_mock
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


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


@pytest.fixture
def on_commit_immediately():
    """Whenever you have a view that looks something like this::

        @transaction.atomic
        def myview(request, pk):
            transaction.on_commit(do_something)
            transaction.on_commit(lambda: do_something_with(pk))
            return http.HttpResponse("All done\n")

    ...then, the post-commit functions `do_something` and `lambda: ...` won't
    be called until after the transaction is successfully committed. However,
    in pytest-django, all transactions are rolled back at the end of the test
    as an optimization to preserve the database fixtures.

    So to have `do_something` and `lambda: ...` execute, within the tests
    you need to use the `on_commit_immediately` as a fixture::

        def test_myview(client, on_commit_immediately):
            response = client.get('/myview/123')
            assert response.status_code == 200

    """

    def run_immediately(some_callable):
        some_callable()

    with mock.patch("django.db.transaction.on_commit") as mocker:
        mocker.side_effect = run_immediately
        yield mocker


@pytest.fixture
def admin_user(db, django_user_model):
    return django_user_model.objects.create(
        username="admin", email="admin@example.com", is_staff=True, is_superuser=True
    )


@pytest.fixture
def mortal_user(db, django_user_model):
    return django_user_model.objects.create(
        username="mortal",
        email="mortal@example.com",
        is_staff=False,
        is_superuser=False,
    )


@pytest.fixture
def admin_client(client, admin_user):
    admin_user.set_password("secret")
    admin_user.save()
    client.login(username=admin_user.username, password="secret")
    return client


@pytest.fixture
def mortal_client(client, mortal_user):
    mortal_user.set_password("secret")
    mortal_user.save()
    client.login(username=mortal_user.username, password="secret")
    return client
