"""Flask web application setup."""
import os

from flask import Flask
from flask_caching import Cache
from werkzeug.middleware.proxy_fix import ProxyFix

from . import app as celery_app

__all__ = ('app', 'cache')


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1, x_prefix=1)

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
