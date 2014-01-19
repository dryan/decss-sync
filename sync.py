#! /usr/bin/env python

import logging, tornado.ioloop, tornado.web, tornado.websocket, uuid, json, copy, os
from urlparse import urlparse
from tornado.options import define, options, parse_command_line

ALLOWED_MASTERS =   os.environ.get('DECSS_SYNC_ALLOWED_MASTERS', '').split(',')

define('port', default = 8888, help = 'run on the given port', type = int)

def get_origin_host(request):
    uri     =   urlparse(request.headers.get('Origin', ''))
    try:
        return uri.netloc.split(':')[0]
    except:
        return ''

class Application(tornado.web.Application):
    def __init__(self):
        handlers    =   [
            (r'/', MainHandler),
            (r'/health-check/', HealthCheck),
        ]
        settings    =   {
            'template_path':    os.path.join(os.path.dirname(__file__), "templates"),
            'xsrf_cookies':     False
        }
        tornado.web.Application.__init__(self, handlers, **settings)

class HealthCheck(tornado.web.RequestHandler):
    def get(self):
        self.render('health-check.json')

class MainHandler(tornado.websocket.WebSocketHandler):
    waiters     =   set()
    cache       =   []
    cache_size  =   200
    id          =   None

    def open(self):
        logging.info('%d waiters open' % (len(self.waiters) + 1))
        self.id =   str(uuid.uuid4())
        MainHandler.waiters.add(self)

    def on_close(self):
        MainHandler.waiters.remove(self)

    @classmethod
    def update_cache(cls, message):
        logging.info('Caching message %r' % message)
        cls.cache.append(message)
        if len(cls.cache) > cls.cache_size:
            cls.cache   =   cls.cache[-cls.cache_size:]

    @classmethod
    def send_updates(cls, message):
        logging.info('Sending message to %d waiters' % len(cls.waiters))
        for waiter in cls.waiters:
            if waiter.id != message.get('sender'):
                try:
                    msg     =   copy.copy(message)
                    del(msg['sender'])
                    waiter.write_message(msg)
                except:
                    logging.error('Error sending message', exc_info = True)

    def on_message(self, message):
        logging.info('got message %r from %r' % (message, get_origin_host(self.request)))
        if get_origin_host(self.request) in ALLOWED_MASTERS:
            # this is a message from the control deck
            message             =   json.loads(message)
            message['sender']   =   self.id
            MainHandler.update_cache(message)
            MainHandler.send_updates(message)

def main():
    parse_command_line()
    app     =   Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()

