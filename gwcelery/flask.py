"""Flask web application setup."""
import os

from flask import Flask
from flask_caching import Cache
from werkzeug.middleware.proxy_fix import ProxyFix

from . import app as celery_app

__all__ = ('app', 'cache')


# Adapted from http://flask.pocoo.org/snippets/69/
class RemoteUserMiddleware:

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        user = environ.pop('HTTP_X_PROXY_REMOTE_USER', None)
        environ['REMOTE_USER'] = user
        return self.app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_prefix=1)
app.wsgi_app = RemoteUserMiddleware(app.wsgi_app)

# Default secret key: secure and random. However, sessions are not preserved
# across different Python processes.
app.config['SECRET_KEY'] = os.urandom(24)

# When running Flask in development mode, reload the application upon changes
# to the templates.
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Set up a server-side cache to store autocomplete responses in order to reduce
# traffic to GraceDB. The cache's backend is the same Redis database that
# Celery uses, although the Redis keys will have a different prefix so that
# they are ignored by Celery.
cache = Cache(app, config={'CACHE_DEFAULT_TIMEOUT': 30,  # lifetime in seconds
                           'CACHE_REDIS_HOST': celery_app.backend.client,
                           'CACHE_TYPE': 'redis'})
