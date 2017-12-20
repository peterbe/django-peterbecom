import os

from django.conf import settings
from elasticsearch_dsl import (
    DocType,
    Boolean,
    Text,
    Integer,
    Date,
    analyzer,
    Keyword,
    token_filter,
)

from peterbecom.base.search import index

synonyms_root = os.path.join(settings.BASE_DIR, 'peterbecom/es-synonyms')
american_british_syns_fn = os.path.join(synonyms_root, 'be-ae.synonyms')
all_synonyms = [
    'go => golang',
    'react => reactjs',
    'angular => angularjs',
    'mongo => mongodb',
    'postgres => postgresql',
    "dont => don't",
]
# The file 'be-ae.synonyms' is a synonym file mapping British to American
# English. For example 'centre => center'.
# And also 'lustre, lustreless => luster, lusterless'
# Because some documents use British English and some use American English
# AND that people who search sometimes use British and sometimes use American,
# therefore we want to match all and anything.
# E.g. "center" should find "...the center of..." and "...the centre for..."
# But also, should find the same when searching for "centre".
# So, rearrange the ba-ae.synonyms file for what's called
# "Simple expansion".
# https://www.elastic.co/guide/en/elasticsearch/guide/current/synonyms-expand-or-contract.html#synonyms-expansion  # noqa
#
with open(american_british_syns_fn) as f:
    for line in f:
        if '=>' not in line or line.strip().startswith('#'):
            continue
        all_synonyms.append(line.strip())


synonym_tokenfilter = token_filter(
    'synonym_tokenfilter',
    'synonym',
    synonyms=all_synonyms,
)


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

text_analyzer = analyzer(
    'text_analyzer',
    tokenizer='standard',
    filter=[
        'standard',
        'lowercase',
        'stop',
        synonym_tokenfilter,
        'snowball',
    ],
    char_filter=['html_strip']
)


@index.doc_type
class BlogItemDoc(DocType):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    # title_autocomplete = Completion()
    title_autocomplete = Text(
        required=True,
        analyzer=edge_ngram_analyzer,
        search_analyzer='standard'
    )
    title = Text(required=True, analyzer=text_analyzer)
    text = Text(analyzer=text_analyzer)
    pub_date = Date()
    categories = Text(fields={'raw': Keyword()})
    keywords = Text(fields={'raw': Keyword()})


@index.doc_type
class BlogCommentDoc(DocType):
    id = Keyword(required=True)
    oid = Keyword(required=True)
    blogitem_id = Integer(required=True)
    approved = Boolean()
    add_date = Date()
    comment = Text(analyzer=text_analyzer)
