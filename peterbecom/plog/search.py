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

synonyms_root = dj_settings.BASE_DIR / "peterbecom/es-synonyms"
# Use str() here because Python 3.5's open() builtin can't take a PosixPath instance.
american_british_syns_fn = str(synonyms_root / "be-ae.synonyms")
all_synonyms = [
    "go => golang",
    "react => reactjs",
    "angular => angularjs",
    "mongo => mongodb",
    "postgres => postgresql",
    "dont => don't",
    "nodejs => node",
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
        if "=>" not in line or line.strip().startswith("#"):
            continue
        all_synonyms.append(line.strip())

SYNONYM_FILE = dj_settings.ELASTICSEARCH_CONFIG_PATH / "peterbecom.synonyms"
with open(SYNONYM_FILE, "w") as f:
    for synonym in all_synonyms:
        f.write(f"{synonym}\n")

synonym_tokenfilter = token_filter(
    "synonym_tokenfilter",
    "synonym",
    # synonyms=all_synonyms
    synonyms_path=str(SYNONYM_FILE.resolve()),
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
