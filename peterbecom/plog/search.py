from django.conf import settings as dj_settings
from django.utils import timezone
from elasticsearch_dsl import (
    Boolean,
    Date,
    Document,
    Float,
    Integer,
    Keyword,
    SearchAsYouType,
    Text,
    analyzer,
    token_filter,
)


# It's useful to be able to turn off synonyms in CI because there it's
# not possible to place a synonyms file in the config directory of the
# elasticsearch server because it's used as an GitHub Action that uses
# a docker image.
if dj_settings.USE_ES_SYNONYM_FILE_NAME:
    synonym_tokenfilter = token_filter(
        "synonym_tokenfilter",
        "synonym",
        synonyms_path=dj_settings.SYNONYM_FILE_NAME,
    )
else:
    synonym_tokenfilter = None


text_analyzer = analyzer(
    "text_analyzer",
    tokenizer="standard",
    filter=["standard", "lowercase", "stop", synonym_tokenfilter, "snowball"]
    if synonym_tokenfilter
    else ["standard", "lowercase", "stop", "snowball"],
    char_filter=["html_strip"],
)
text_analyzer = analyzer(
    "text_analyzer",
    tokenizer="standard",
    filter=["lowercase", "stop", synonym_tokenfilter, "snowball"]
    if synonym_tokenfilter
    else ["lowercase", "stop", "snowball"],
    char_filter=["html_strip"],
)
search_term_analyzer = analyzer(
    "search_term_analyzer",
    tokenizer="standard",
    filter=["lowercase", "snowball"],
)


def timestamped(prefix):
    return f"{prefix}_{timezone.now().strftime('%Y%m%d%H%M%S')}"


class BlogItemDoc(Document):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    # https://github.com/elastic/elasticsearch-dsl-py/blob/master/examples/search_as_you_type.py
    title_autocomplete = SearchAsYouType(max_shingle_size=3)
    title = Text(
        required=True, analyzer=text_analyzer, term_vector="with_positions_offsets"
    )
    text = Text(analyzer=text_analyzer, term_vector="with_positions_offsets")
    pub_date = Date()
    categories = Text(fields={"raw": Keyword()})
    keywords = Text(fields={"raw": Keyword()})
    popularity = Float()

    class Index:
        name = timestamped(dj_settings.ES_BLOG_ITEM_INDEX)
        settings = dj_settings.ES_BLOG_ITEM_INDEX_SETTINGS


class BlogCommentDoc(Document):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    blogitem_id = Integer(required=True)
    approved = Boolean()
    add_date = Date()
    comment = Text(analyzer=text_analyzer, term_vector="with_positions_offsets")
    popularity = Float()

    class Index:
        name = timestamped(dj_settings.ES_BLOG_COMMENT_INDEX)
        settings = dj_settings.ES_BLOG_COMMENT_INDEX_SETTINGS


class SearchTermDoc(Document):
    term = Text(
        required=True,
        analyzer=search_term_analyzer,
        term_vector="with_positions_offsets",
    )
    popularity = Float()
    foo_bar = Boolean()

    class Index:
        name = timestamped(dj_settings.ES_SEARCH_TERM_INDEX)
        settings = dj_settings.ES_SEARCH_TERM_INDEX_SETTINGS


def swap_alias(connection, index_name, alias):
    assert index_name.startswith(alias + "_")
    alias_updates = [
        {
            "add": {
                "index": index_name,
                "alias": alias,
            }
        }
    ]
    for name in connection.indices.get_alias():
        if name.startswith(f"{alias}_"):
            if name != index_name:
                alias_updates.append({"remove_index": {"index": name}})
    connection.indices.update_aliases(body={"actions": alias_updates})
