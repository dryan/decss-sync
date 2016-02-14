import tornado.wsgi
from sync import application as app

application = tornado.wsgi.WSGIAdapter(app)
