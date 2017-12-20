from elasticsearch_dsl import (
    DocType,
    Float,
    Text,
    Integer,
    Date,
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


@index.doc_type
class PodcastDoc(DocType):
    id = Keyword(required=True)
    thumbnail_348 = Keyword()
    thumbnail_160 = Keyword()
    times_picked = Integer()
    episodes_count = Integer()
    episodes_seconds = Float()
    slug = Keyword(required=True, index=False)
    name = Text(
        required=True,
        analyzer=edge_ngram_analyzer,
        search_analyzer='standard'
    )
    link = Keyword()
    subtitle = Text()
    summary = Text()
    last_fetch = Date()
    latest_episode = Date()
    modified = Date()
