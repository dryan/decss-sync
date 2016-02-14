import tornado.wsgi
import wsgiref.simple_server
from sync import Application

def application():
    app = Application()
    wsgi_app = tornado.wsgi.WSGIAdapter(app)
    server = wsgiref.simple_server.make_server('', 8888, wsgi_app)
    server.serve_forever()
