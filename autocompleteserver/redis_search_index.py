# coding=utf-8

# taken and adopted from
# http://engineering.getglue.com/post/36667374830/autocomplete-search-with-redis

import re
from functools import partial
from itertools import imap, izip, product

from unidecode import unidecode
#from redis import Redis

#from peterbecom.apps.homepage.utils import STOPWORDS_TUPLE as STOPWORDS
from tornado import gen


class PrefixTree(object):
    '''
    Tree used to store a wordlist. Words are factored according to their common prefixes.

    For performance reasons the PrefixTree is only partially build and will be further constructed
    by need.
    '''
    def __init__(self, char = '', parent = None):
        self.char      = char
        self.parent    = parent
        self.is_word   = False
        self._children = {}
        self._words    = set()

    def _get_children(self):
        if self._words:
            self._create_children()
        return self._children

    children = property(_get_children)

    def _create_children(self):
        for tree, word in self._words:
            tree.insert(word)
        self._words = set()

    def _tolist(self):
        if self.is_word:
            yield self.trace()
        for p in self.children.values():
            for s in p._tolist():
                yield s

    def __iter__(self):
        return self._tolist()

    def insert(self, value):
        if value:
            c = value[0]
            tree = self._children.get(c)
            if tree is None:
                tree = PrefixTree(c, self)
                self._children[c] = tree
            if len(value) == 1:
                tree.is_word = True
            tree._words.add((tree,value[1:]))
        else:
            self.is_word = True

    def __contains__(self, value):
        if value:
            if value in self._words:
                return True
            c = value[0]
            if c in self._children:
                return value[1:] in self._children[c]
            return False
        return True

    def __len__(self):
        if self.parent is not None:
            return len(self.parent)+1
        return 0

    def trace(self):
        if self.parent is not None:
            return self.parent.trace()+self.char
        return self.char


def update_visited(ptree, visited):
    visited[ptree][-1] = 0
    T = ptree.parent
    while T is not None and T.char!='':
        if len(T.children) == 1:
            visited[T][-1] = 0
            T = T.parent
        else:
            return

def is_visited(i, T, k, visited):
    d = visited.get(T, {})
    if -1 in d:
        return True
    m = d.get(i,-1)
    if k>m:
        d[i] = k
        visited[T] = d
        return False
    return True


def fuzzy_match(S, ptree, k, i=0, visited = None, N = 0):
    '''
    Searches for strings in a PrefixTree ( wordlist ) with a bound number of errors.

    More precisely: computes all strings T contained in ptree with a distance dist(S, T)<=k.
    '''
    trees = set()
    # handles root node of a PrefixTree
    if ptree.char == '' and ptree.children:
        N = len(S)
        S+='\0'*(k+1)
        visited = {}
        for T in ptree.children.values():
            trees.update(fuzzy_match(S, T, k, i, visited, N))
        return trees

    # already tried
    if is_visited(i, ptree, k, visited):
        return []

    # can't match ...
    if k == -1 or (k == 0 and S[i] != ptree.char):
        return []

    if ptree.is_word and (N-i<=k or (N-i<=k+1 and ptree.char == S[i])):
        trees.add(ptree.trace())
        if not ptree.children:
            update_visited(ptree, visited)
            return trees

    if ptree.char!=S[i]:
        trees.update(fuzzy_match(S, ptree, k-1, i+1, visited, N))

    for c in ptree.children:
        if ptree.char == S[i]:
            trees.update(fuzzy_match(S, ptree.children[c], k, i+1, visited, N))
        else:
            trees.update(fuzzy_match(S, ptree.children[c], k-1, i+1, visited, N))
        trees.update(fuzzy_match(S, ptree.children[c], k-1, i, visited, N))
    return trees


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
        chars = '"[]():;?!,\'-'
        translation = dict((ord(c), u' ') for c in chars)
        def translate(text):
            if isinstance(text, unicode):
                translated = text.translate(translation)
            else:
                translated = text.translate(None, chars)
            return translated
        strips = '.'
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

    @gen.coroutine
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
        if not terms:
            raise gen.Return(final)
        term_groups = [terms]

        trie = self.get_ptrie()
        for term in terms:
            new_group = []
            for t in fuzzy_match(term, trie, 1):
                print "T", (term, t)
                new_group.append(t or term)
            if new_group not in term_groups:
                term_groups.append(new_group)
                #if t not in terms:
                #    terms.append(t)
        #print "TERMS"
        #print terms

        def flatten(seq):
            nseq = []
            for item in seq:
                if isinstance(item, list):
                    nseq.extend(flatten(item))
                else:
                    nseq.append(item)
            return nseq

        final = {
            'terms': flatten(term_groups),
            'results': []
        }
        print term_groups
        all_results_sorted = []
        for terms in term_groups:
            with self._r.pipeline() as pipe:
                pipe.zinterstore('$tmp', terms, aggregate='max')
                pipe.zrevrange('$tmp', 0, n, True)
                # response = pipe.execute()
                response = yield gen.Task(pipe.execute)
                scored_ids = response[1]
            if not scored_ids:
                continue
                # raise gen.Return(final)
            titles = yield gen.Task(self._r.hmget, '$titles', [i[0] for i in scored_ids])
            results = imap(
                lambda x: x[0] + (titles[x[1]],),
                izip(scored_ids, titles)
            )
            # final['results'] = sorted(
            # results_sorted = sorted(
            #     results,
            #     key=lambda r: query_score(terms, r[2]) * r[1],
            #     reverse=True
            # )
            all_results_sorted.extend(results)
        print "all_results_sorted"
        print all_results_sorted
        results_sorted = sorted(
            all_results_sorted,
            key=lambda r: r[1],
            reverse=True
        )

        final['results'] = results_sorted[:n]
        raise gen.Return(final)

    def get_ptrie(self):
        trie = PrefixTree()
        words = [
            'mongo',
            'test',
            'group',
            'groups',
            'great',
            'google',
        ]
        for w in words:
            trie.insert(w)
        return trie
