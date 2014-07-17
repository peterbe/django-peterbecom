# coding=utf-8

# taken and adopted from
# http://engineering.getglue.com/post/36667374830/autocomplete-search-with-redis

from functools import partial
from itertools import imap, izip, product

from unidecode import unidecode
from redis import Redis

from peterbecom.apps.homepage.utils import STOPWORDS_TUPLE as STOPWORDS


class RedisSearchIndex(object):
    """Autocomplete search index.

    >>> index = RedisSearchIndex(Redis())
    >>> index.add_item('tv_shows/twin_peaks', 'Twin Peaks', 1000)
    >>> index.search('twin')
    ('tv_shows/twin_peaks', 1000.0, 'Twin Peaks')
    """

    def __init__(self, r, min_word_length=1):
        """Initialize the index with a Redis instance."""
        self._r = r
        self.min_word_length = min_word_length

    def _clean_words(self, title, filter_stopwords=False):
        """Generate normalized alphanumeric words for a given title."""
        chars = '"[]():;?!,'
        translation = dict((ord(c), u'') for c in chars)
        def translate(text):
            if isinstance(text, unicode):
                return text.translate(translation)
            else:
                return text.translate(None, chars)
        strips = '.\''
        words = [
            x.strip(strips)
            for x in translate(title).split()
        ]
        for word in words:
            if len(word) >= self.min_word_length:
                if filter_stopwords and word.lower() not in STOPWORDS:
                    continue
                # if the word contains non-ascii characters, try to convert
                # it to a ascii equivalent so that it's possible to type
                # "naive" when you don't even know how to type "naïve"
                try:
                    word.encode('ascii')
                except UnicodeEncodeError:
                    # it contains non-ascii characters
                    ascii_word = unidecode(word)
                    yield unicode(ascii_word).lower()
                yield word.lower()
            # yield ''.join(c for c in word if c.isalnum())

    def _prefixes(self, title, filter_stopwords=False):
        """Generate the prefixes for a given title."""
        for word in self._clean_words(title, filter_stopwords=filter_stopwords):
            prefixer = partial(word.__getslice__, 0)
            for prefix in imap(prefixer, range(1, len(word) + 1)):
                yield prefix

    def add_item(self, item_id, item_title, score, filter_stopwords=False):
        """Add an item to the autocomplete index."""
        with self._r.pipeline() as pipe:
            for prefix in self._prefixes(item_title, filter_stopwords=filter_stopwords):
                pipe.zadd(prefix, item_id, score)
            pipe.hset('$titles', item_id, item_title)
            pipe.execute()
        return True

    def search(self, query, n=500, filter_stopwords=False):
        """Return the top N objects from the autocomplete index."""

        def query_score(terms, title):
            """Score the search query based on the title."""

            def term_score(term, word):
                # print (term, word)
                if word.startswith(term):
                    return float(len(term)) / len(word)
                else:
                    return 0.0

            words = list(self._clean_words(title))
            return sum(term_score(t, w) for t, w in product(terms, words))

        terms = list(
            self._clean_words(query, filter_stopwords=filter_stopwords)
        )
        final = {
            'terms': terms,
            'results': []
        }
        if not terms:
            return final
        with self._r.pipeline() as pipe:
            pipe.zinterstore('$tmp', terms, aggregate='max')
            pipe.zrevrange('$tmp', 0, n, withscores=True)
            response = pipe.execute()
            scored_ids = response[1]
        if not scored_ids:
            return final
        titles = self._r.hmget('$titles', *[i[0] for i in scored_ids])
        titles = [unicode(t, 'utf-8') for t in titles]
        results = imap(lambda x: x[0] + (x[1],), izip(scored_ids, titles))
        final['results'] = sorted(
            results,
            key=lambda r: query_score(terms, r[2]) * r[1],
            reverse=True
        )
        return final
