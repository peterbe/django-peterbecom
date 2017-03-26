from elasticsearch_dsl import (
    DocType,
    Boolean,
    Text,
    Integer,
    Date,
    # Index,
    analyzer,
    Keyword,
    token_filter,
)

from peterbecom.base.search import index


edge_ngram_analyzer = analyzer(
    'edge_ngram_analyzer',
    type='custom',
    tokenizer='standard',
    filter=[
        'lowercase',
        token_filter(
            'edge_ngram_filter', type='edgeNGram',
            min_gram=1, max_gram=20
        )
    ]
)


html_strip = analyzer(
    'html_strip',
    tokenizer='standard',
    filter=['standard', 'lowercase', 'stop', 'snowball'],
    char_filter=['html_strip']
)


class BlogItemDoc(DocType):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    title = Text(
        required=True,
        analyzer=edge_ngram_analyzer,
        search_analyzer='standard'
    )
    text = Text(analyzer=html_strip)
    pub_date = Date()
    categories = Text(fields={'raw': Keyword()})
    keywords = Text(fields={'raw': Keyword()})


class BlogCommentDoc(DocType):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    blogitem_id = Integer(required=True)
    approved = Boolean()
    add_date = Date()
    comment = Text(analyzer=html_strip)


# create an index and register the doc types
# index = Index(settings.ES_INDEX)
# index.settings(**settings.ES_INDEX_SETTINGS)
index.doc_type(BlogItemDoc)
index.doc_type(BlogCommentDoc)
