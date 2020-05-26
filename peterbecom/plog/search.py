from django.conf import settings as dj_settings
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


synonym_tokenfilter = token_filter(
    "synonym_tokenfilter",
    "synonym",
    # synonyms=all_synonyms
    synonyms_path=dj_settings.SYNONYM_FILE_NAME,
)


text_analyzer = analyzer(
    "text_analyzer",
    tokenizer="standard",
    filter=["standard", "lowercase", "stop", synonym_tokenfilter, "snowball"],
    char_filter=["html_strip"],
)
text_analyzer = analyzer(
    "text_analyzer",
    tokenizer="standard",
    filter=["lowercase", "stop", synonym_tokenfilter, "snowball"],
    char_filter=["html_strip"],
)


class BlogItemDoc(Document):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    # https://github.com/elastic/elasticsearch-dsl-py/blob/master/examples/search_as_you_type.py
    title_autocomplete = SearchAsYouType(max_shingle_size=3)
    title = Text(required=True, analyzer=text_analyzer)
    text = Text(analyzer=text_analyzer)
    pub_date = Date()
    categories = Text(fields={"raw": Keyword()})
    keywords = Text(fields={"raw": Keyword()})
    popularity = Float()

    class Index:
        name = dj_settings.ES_BLOG_ITEM_INDEX
        settings = dj_settings.ES_BLOG_ITEM_INDEX_SETTINGS


class BlogCommentDoc(Document):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    blogitem_id = Integer(required=True)
    approved = Boolean()
    add_date = Date()
    comment = Text(analyzer=text_analyzer)
    popularity = Float()

    class Index:
        name = dj_settings.ES_BLOG_COMMENT_INDEX
        settings = dj_settings.ES_BLOG_COMMENT_INDEX_SETTINGS
