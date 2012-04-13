import logging
import time
from django.conf import settings
from django.core.cache import parse_backend_uri

try:
    import redis as redislib
except:
    redislib = None

connections = {}

if not connections:  # don't set this repeatedly
    for alias, backend in settings.REDIS_BACKENDS.items():
        _, server, params = parse_backend_uri(backend)
        try:
            socket_timeout = float(params.pop('socket_timeout'))
        except (KeyError, ValueError):
            socket_timeout = None
        password = params.pop('password', None)
        if ':' in server:
            host, port = server.split(':')
            try:
                port = int(port)
            except (ValueError, TypeError):
                port = 6379
        else:
            host = 'localhost'
            port = 6379

        connections[alias] = redislib.Redis(host=host, port=port, db=0,
                                            password=password,
                                            socket_timeout=socket_timeout)


def wrapped_function(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except redislib.ConnectionError:
            time.sleep(1)
            logging.debug("redis ConnectionError, sleeping 1 second")
            try:
                return func(*args, **kwargs)
            except redislib.ConnectionError:
                time.sleep(2)
                logging.debug("redis ConnectionError, sleeping 2 second")
                try:
                    return func(*args, **kwargs)
                except redislib.ConnectionError:
                    logging.debug("redis ConnectionError, still :(")
                    raise
    return wrapper

class ReConnectionConnectionWrapper(object):
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, key):
        return wrapped_function(getattr(self.connection, key))

def get_redis_connection(alias='master', reconnection_wrapped=False):
    if reconnection_wrapped:
        return ReConnectionConnectionWrapper(connections[alias])
    return connections[alias]

def mock_redis():
    ret = dict(connections)
    for key in connections:
        connections[key] = MockRedis()
    return ret


def reset_redis(cxn):
    for key, value in cxn.items():
        connections[key] = value


class StringDict(dict):
    """A dict that converts all keys to strings automatically (like redis)."""

    def __setitem__(self, key, value):
        if not isinstance(key, basestring):
            key = unicode(key)
        super(StringDict, self).__setitem__(key, value)

    def __getitem__(self, key):
        if not isinstance(key, basestring):
            key = unicode(key)
        super(StringDict, self).__getitem__(key)


class MockRedis(object):
    """A fake redis we can use for testing."""

    def __init__(self):
        self.kv = StringDict()

    def flushall(self):
        self.kv.clear()

    def pipeline(self, **kw):
        return self

    def execute(self):
        pass

    ## Keys.

    def get(self, key):
        return self.kv.get(key)

    def incr(self, key):
        bump = (self.get(key) or 0) + 1
        self.set(key, bump)
        return bump

    def set(self, key, val):
        self.kv[key] = val

    def setnx(self, key, val):
        if key not in self.kv:
            self.set(key, val)
            return True
        return False

    def delete(self, key):
        if key in self.kv:
            del self.kv[key]
            return True
        return False

    ## Sets.

    def sadd(self, key, val):
        v = self.kv.setdefault(key, set())
        if isinstance(v, set):
            v.add(val)
            return True
        return False

    def srem(self, key, val):
        v = self.kv.get(key, set())
        v.discard(val)

    def smembers(self, key):
        v = self.kv.get(key, set())
        if isinstance(v, set):
            return v

    def sinter(self, keys):
        sets = [self.kv.get(key, set()) for key in keys]
        return reduce(lambda x, y: x & y, sets)

    ## Hashes.

    def hmget(self, name, keys):
        db = self.kv.get(name, StringDict())
        return [db.get(key) for key in keys]

    def hmset(self, name, dict_):
        db = self.kv.setdefault(name, StringDict())
        db.update(dict_)

    def hgetall(self, name):
        return self.kv.get(name, StringDict())

    def hset(self, name, key, value):
        db = self.kv.setdefault(name, StringDict())
        db[key] = value

    def hsetnx(self, name, key, value):
        db = self.kv.setdefault(name, StringDict())
        if key not in db:
            db[key] = value
            return True
        return False

    def hget(self, name, key):
        return self.kv.get(name, StringDict()).get(key)

    def hdel(self, name, key):
        db = self.kv.get(name, StringDict())
        if key in db:
            del db[key]

    def hlen(self, name):
        return len(self.kv.get(name, StringDict()))

    def hincrby(self, name, key, amount=1):
        db = self.kv.get(name, StringDict())
        val = db.setdefault(key, 0)
        db[key] = val + amount

    ## Lists.

    def rpush(self, name, *vals):
        list_ = self.kv.get(name, [])
        list_.extend(vals)
        self.kv[name] = list_
        return len(list_)

    def llen(self, name):
        return len(self.kv.get(name, []))

    def lindex(self, name, index):
        try:
            return self.kv.get(name, [])[index]
        except IndexError:
            return None
