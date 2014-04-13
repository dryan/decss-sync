#! /usr/bin/env python

import logging, tornado.ioloop, tornado.web, tornado.websocket, tornado.auth, torndb, json, copy, os, MySQLdb
from urlparse import urlparse
from tornado.options import define, options, parse_command_line

define('port', default = 8888, help = 'run on the given port', type = int)

def get_origin_host(request):
    uri     =   urlparse(request.headers.get('Origin', ''))
    try:
        return uri.netloc.split(':')[0]
    except:
        return ''

class TwitterHandler(tornado.web.RequestHandler, tornado.auth.TwitterMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument('oauth_token', None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect()

    def _on_auth(self, openid):
        if not openid:
            raise tornado.web.HTTPError(500, 'Twitter auth failed')

        user    =   self.application.db.get('SELECT * FROM `users` WHERE `username`=%s', openid.get('access_token').get('screen_name'))
        if user is None:
            self.application.db.execute('INSERT INTO `users` (username, access_key, access_token) VALUES (%s, %s, %s)', openid.get('access_token').get('screen_name'), openid.get('access_token').get('key'), openid.get('access_token').get('secret'))
            user    =   self.application.db.get('SELECT * FROM `users` WHERE `username`=%s', openid.get('access_token').get('screen_name'))
        self.set_secure_cookie('decss_user', user.get('username'))
        return self.redirect('/')

class AuthUserHandler(tornado.web.RequestHandler):
    user    =   None
    _cached =   False # used to make sure we only hit the db once per request

    def get_current_user(self):
        if not self._cached and self.get_secure_cookie('decss_user', None):
            self.user   =   self.application.db.get('SELECT * FROM `users` WHERE `username`=%s', self.get_secure_cookie('decss_user'))
        self._cached    =   True
        return self.user

class Application(tornado.web.Application):
    def __init__(self):
        handlers    =   [
            (r'/', MainHander),
            (r'/add/', DeckHandler),
            (r'/socket/', SocketHandler),
            (r'/health-check/', HealthCheck),
            (r'/login/', TwitterHandler),
            (r'/logout/', LogoutHandler),
        ]
        settings    =   {
            'template_path':            os.path.join(os.path.dirname(__file__), "templates"),
            'xsrf_cookies':             True,
            'twitter_consumer_key':     os.environ.get('DECSS_SYNC_TWITTER_API_KEY', None),
            'twitter_consumer_secret':  os.environ.get('DECSS_SYNC_TWITTER_API_SECRET', None),
            'cookie_secret':            os.environ.get('DECSS_SYNC_COOKIE_SECRET'),
            'segmentio_write_key':      os.environ.get('DECSS_SYNC_SEGMENTIO_WRITE_KEY', None),
        }
        self.login_url  =   '/login/'
        self.db         =   torndb.Connection(
            os.environ.get('DECSS_SYNC_DATABASE_HOST'),
            os.environ.get('DECSS_SYNC_DATABASE_NAME'),
            os.environ.get('DECSS_SYNC_DATABASE_USER'),
            os.environ.get('DECSS_SYNC_DATABASE_PASSWORD')
        )
        tornado.web.Application.__init__(self, handlers, **settings)

    def check_owner(self, user, deck_id):
        return user and self.db.get('SELECT * FROM `decks` WHERE `uuid`=%s AND `owner`=%s', deck_id, user.get('id'))

class HealthCheck(tornado.web.RequestHandler):
    def get(self):
        self.render('health-check.json')

class SocketHandler(tornado.websocket.WebSocketHandler, AuthUserHandler):
    waiters     =   set()
    cache       =   []
    cache_size  =   200
    id          =   None
    deck_id     =   None
    is_owner    =   False

    def open(self):
        logging.info('%d waiters open' % (len(self.waiters) + 1))
        self.id =   os.urandom(16).encode('hex')
        SocketHandler.waiters.add(self)
        if self.deck_id:
            SocketHandler.update_viewer_count(self.deck_id)

    def on_close(self):
        SocketHandler.waiters.remove(self)
        if self.deck_id:
            SocketHandler.update_viewer_count(self.deck_id)

    @classmethod
    def update_viewer_count(cls, deck_id = None):
        viewers =   0
        for waiter in cls.waiters:
            if waiter.deck_id == deck_id:
                viewers +=  1
        message =   {
            'type':     'viewers',
            'viewers':  viewers,
            'deck_id':  deck_id,
        }
        SocketHandler.update_cache(message)
        SocketHandler.send_updates(message)

    @classmethod
    def update_cache(cls, message):
        logging.info('Caching message %r' % message)
        cls.cache.append(message)
        if len(cls.cache) > cls.cache_size:
            cls.cache   =   cls.cache[-cls.cache_size:]

    @classmethod
    def send_updates(cls, message):
        for waiter in cls.waiters:
            if message.get('type', '') == 'sync' and waiter.id != message.get('sender') and waiter.deck_id == message.get('id', 0): 
                logging.info('Sending sync message to waiter %s for deck %s' % (message.get('sender'), waiter.deck_id))
                # this is a sync message and the waiter is not the sender
                try:
                    msg     =   copy.copy(message)
                    del(msg['sender'])
                    waiter.write_message(msg)
                except:
                    logging.error('Error sending message', exc_info = True)
            elif message.get('type', '') == 'pong' and waiter.id == message.get('sender'):
                logging.info('Sending pong message to %s for deck %s' % (message.get('sender'), waiter.deck_id))
                try:
                    msg     =   copy.copy(message)
                    del(msg['sender'])
                    waiter.write_message(msg)
                except:
                    logging.error('Error sending message', exc_info = True)
            elif message.get('type', '') == 'viewers' and waiter.is_owner and waiter.deck_id == message.get('deck_id', 0):
                logging.info('Sending viewers message to %s' % waiter.id)
                try:
                    waiter.write_message(message)
                except:
                    logging.error('Error sending message', exc_info = True)

    def on_message(self, message):
        logging.info('got message %r from %r' % (message, get_origin_host(self.request)))
        message =   json.loads(message)
        user    =   self.get_current_user()
        if message.get('type', '') == 'sync' and self.application.check_owner(user, message.get('id', 0)):
                # this is a message from the owner
                message['sender']   =   self.id
                SocketHandler.update_cache(message)
                SocketHandler.send_updates(message)
        elif message.get('type', '') == 'ping':
            # this user just connected, send an ack back to grant control if this is the owner
            self.deck_id    =   message.get('id', 0)
            self.is_owner   =   bool(self.application.check_owner(user, self.deck_id))
            message         =   {
                'type':     'pong',
                'sender':   self.id,
                'auth':     self.is_owner
            }
            SocketHandler.update_cache(message)
            SocketHandler.send_updates(message)
            SocketHandler.update_viewer_count(self.deck_id)


class MainHander(AuthUserHandler):
    def get(self):
        user = self.get_current_user()
        if user:
            self.render('dashboard.html', user = user, decks = self.application.db.query('SELECT * FROM `decks` WHERE `owner`=%s ORDER BY `id`', user.get('id')), host = self.request.host, segmentio_write_key = self.application.settings.get('segmentio_write_key', None))
        else:
            self.render('home.html', user = user, segmentio_write_key = self.application.settings.get('segmentio_write_key', None))

class DeckHandler(AuthUserHandler):
    def get(self):
        user    =   self.get_current_user()
        if not user:
            return self.redirect('/')
        self.render('deck-form.html', user = user, errors = False)

    def post(self):
        # if not self.check_xsrf_cookie():
        #     raise tornado.web.HTTPError(403, 'Access Denied')
        user    =   self.get_current_user()
        if not user:
            return self.redirect('/')
        name    =   MySQLdb.escape_string(self.get_argument('name', ''))
        if not name:
            self.render('deck-form.html', errors = True)
            return
        self.application.db.execute('INSERT INTO `decks` (name, owner, uuid) VALUES (%s, %s, %s)', name, user.get('id'), os.urandom(16).encode('hex'))
        return self.redirect('/')

class LogoutHandler(AuthUserHandler):
    def get(self):
        self.clear_cookie('decss_user')
        return self.redirect('/')

def main():
    parse_command_line()
    app     =   Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()

