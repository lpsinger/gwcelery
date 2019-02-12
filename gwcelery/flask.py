"""Flask web application setup."""
import os

from flask import Flask
from flask_caching import Cache

from . import app as celery_app

__all__ = ('app', 'cache')


# from http://flask.pocoo.org/snippets/35/
class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app, script_name=None):
        self.app = app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '') or self.script_name
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)
app.wsgi_app.script_name = os.environ.get('FLASK_URL_PREFIX')

# Default secret key: secure and random. However, sessions are not preserved
# across different Python processes.
app.config['SECRET_KEY'] = os.urandom(24)

# Set up a server-side cache to store autocomplete responses in order to reduce
# traffic to GraceDb. The cache's backend is the same Redis database that
# Celery uses, although the Redis keys will have a different prefix so that
# they are ignored by Celery.
cache = Cache(app, config={'CACHE_DEFAULT_TIMEOUT': 30,  # lifetime in seconds
                           'CACHE_REDIS_HOST': celery_app.backend.client,
                           'CACHE_TYPE': 'redis'})
