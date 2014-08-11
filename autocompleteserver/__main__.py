#!/usr/bin/env python

import tornado.ioloop
import tornado.web
import tornado.gen
import tornadoredis

from tornado.options import define, options

from redis_search_index import RedisSearchIndex


define("debug", default=False, help="run in debug mode", type=bool)
define("port", default=8888, help="run on the given port", type=int)


c = tornadoredis.Client(selected_db=9)
c.connect()


class MainHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        q = self.get_argument('q')
        if not q:
            self.write([])
            return
        n = int(self.get_argument('n', 10))
        r = RedisSearchIndex(c)
        final = yield r.search(q, n=n)
        self.write(final)


def app(debug=False):
    return tornado.web.Application([
        (r"/", MainHandler),
    ], debug=debug)


if __name__ == "__main__":
    tornado.options.parse_command_line()
    print "Starting tornado on port", options.port
    application = app(options.debug)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
