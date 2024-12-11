import mock
import pytest
import requests_mock
from django.core.cache import cache
from elasticsearch_dsl.connections import connections

from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc, swap_alias

TEST_ES_BLOG_COMMENT_INDEX = "test_blog_comments"
TEST_ES_BLOG_ITEM_INDEX = "test_blog_items"
TEST_ES_SEARCH_TERM_INDEX = "test_search_terms"


@pytest.fixture(autouse=True)
def force_elasticsearch_test_index(settings):
    settings.ES_BLOG_ITEM_INDEX = TEST_ES_BLOG_ITEM_INDEX
    settings.ES_BLOG_COMMENT_INDEX = TEST_ES_BLOG_COMMENT_INDEX
    settings.ES_SEARCH_TERM_INDEX = TEST_ES_SEARCH_TERM_INDEX


@pytest.fixture(scope="session", autouse=True)
def assert_elasticsearch_index():
    es = connections.get_connection()

    blog_item_index = BlogItemDoc._index
    blog_item_index._name = BlogItemDoc.Index.get_refreshed_name(
        TEST_ES_BLOG_ITEM_INDEX
    )
    blog_item_index.create()
    swap_alias(es, blog_item_index._name, TEST_ES_BLOG_ITEM_INDEX)

    blog_comment_index = BlogCommentDoc._index
    blog_comment_index._name = BlogCommentDoc.Index.get_refreshed_name(
        TEST_ES_BLOG_COMMENT_INDEX
    )
    blog_comment_index.create()
    swap_alias(es, blog_comment_index._name, TEST_ES_BLOG_COMMENT_INDEX)

    # The reason SearchTermDoc is not set up here is because it's never
    # incrementally populated (e.g. new comment => immediately add
    # it to the index)

    yield

    blog_item_index.delete()
    blog_comment_index.delete()


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
