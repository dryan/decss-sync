import tornado.wsgi
import wsgiref.simple_server
from sync import Application

if __name__ == '__main__':
    application = Application()
    wsgi_app = tornado.wsgi.WSGIAdapter(application)
    server = wsgiref.simple_server.make_server('', 8888, wsgi_app)
    server.serve_forever()
