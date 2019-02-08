"""Flask web application for manually triggering certain tasks."""
import argparse
import datetime
import os
import re

from astropy.time import Time
from celery.bin.base import Command
import click
import click.testing
from flask import (flash, Flask, jsonify, redirect, render_template, request,
                   url_for)
from flask_caching import Cache
from flask.cli import FlaskGroup
from ligo.gracedb.rest import HTTPError as GraceDbHTTPError

from . import app as celery_app
from .tasks import first2years, gracedb, orchestrator


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


@app.route('/')
def index():
    return render_template('index.html')


def take_n(n, iterable):
    for i, item in enumerate(iterable):
        if i >= n:
            break
        yield item


# Regular expression for parsing query strings
# that look like GraceDb superevent names.
typeahead_graceid_regex = re.compile(
    r'(?P<prefix>[MT]?)S?(?P<date>\d{0,6})(?P<suffix>[a-z]*)',
    re.IGNORECASE)


@app.route('/typeahead_superevent_id')
@cache.cached(query_string=True)
def typeahead_superevent_id():
    """Search GraceDb for superevents by ID.

    This involves some date parsing because GraceDb does not support directly
    searching for superevents by ID substring."""

    max_results = 8  # maximum number of results to return
    batch_results = 32  # batch size for results from server

    term = request.args.get('superevent_id')
    match = typeahead_graceid_regex.fullmatch(term) if term else None

    if match:
        # Determine GraceDb event category from regular expression.
        prefix = match['prefix'].upper() + 'S'
        category = {'T': 'test', 'M': 'MDC'}.get(
            match['prefix'].upper(), 'production')

        # Determine start date from regular expression by padding out
        # the partial date with missing digits defaulting to 000101.
        date_partial = match['date']
        date_partial_length = len(date_partial)
        try:
            date_start = datetime.datetime.strptime(
                date_partial + '000101'[date_partial_length:], '%y%m%d')
        except ValueError:  # invalid date
            return jsonify([])

        # Determine end date from regular expression by adding a very
        # loose upper bound on the number of days until the next
        # digit in the date rolls over. No need to be exact here.
        date_end = date_start + datetime.timedelta(
            days=[36600, 3660, 366, 320, 32, 11, 1.1][date_partial_length])

        # Determine GraceDb event suffix from regular expression.
        suffix = match['suffix'].lower()
    else:
        prefix = 'S'
        category = 'production'
        date_end = datetime.datetime.utcnow()
        date_start = date_end - datetime.timedelta(days=7)
        date_partial = ''
        date_partial_length = 0
        suffix = ''

    # Query GraceDb.
    query = 'category: {} t_0: {} .. {}'.format(
        category, Time(date_start).gps, Time(date_end).gps)
    response = gracedb.client.superevents(
        query, orderby='superevent_id', count=batch_results)

    # Filter superevent IDs that match the search term.
    regex = re.compile(r'{}{}\d{{{}}}{}[a-z]*'.format(
        prefix, date_partial, 6 - date_partial_length, suffix))
    superevent_ids = (
        superevent['superevent_id'] for superevent
        in response if regex.fullmatch(superevent['superevent_id']))

    # Return only the first few matches.
    return jsonify(list(take_n(max_results, superevent_ids)))


def _search_by_tag_and_filename(superevent_id, filename, extension, tag):
    try:
        records = gracedb.client.logs(superevent_id).json()['log']
        return [
            record['filename'] for record in records
            if tag in record['tag_names']
            and record['filename'].startswith(filename)
            and record['filename'].endswith(extension)]
    except GraceDbHTTPError as e:
        # Ignore 404 errors from server
        if e.status == 404:
            return []
        else:
            raise


@app.route('/typeahead_skymap_filename')
@cache.cached(query_string=True)
def typeahead_skymap_filename():
    return jsonify(_search_by_tag_and_filename(
        request.args.get('superevent_id') or '',
        request.args.get('filename') or '',
        '.fits.gz', 'sky_loc'
    ))


@app.route('/typeahead_source_classification_filename')
@cache.cached(query_string=True)
def typeahead_source_classification_filename():
    return jsonify(_search_by_tag_and_filename(
        request.args.get('superevent_id') or '',
        request.args.get('filename') or '',
        '.json', 'em_bright'
    ))


@app.route('/typeahead_p_astro_filename')
@cache.cached(query_string=True)
def typeahead_p_astro_filename():
    return jsonify(_search_by_tag_and_filename(
        request.args.get('superevent_id') or '',
        request.args.get('filename') or '',
        '.json', 'p_astro'
    ))


@app.route('/send_update_gcn', methods=['POST'])
def send_update_gcn():
    keys = ('superevent_id', 'skymap_filename',
            'source_classification_filename', 'p_astro_filename')
    superevent_id, *_ = args = tuple(request.form.get(key) for key in keys)
    if all(args):
        app.logger.info(
            'Calling update_alert%r', args)
        orchestrator.update_alert(*args)
        flash('Queued update alert for {}.'.format(superevent_id), 'success')
    else:
        flash('No alert sent. Please fill in all fields.', 'danger')
    return redirect(url_for('index'))


@app.route('/send_mock_event', methods=['POST'])
def send_mock_event():
    first2years.upload_event.delay()
    flash('Queued a mock event.', 'success')
    return redirect(url_for('index'))


@click.group(cls=FlaskGroup, create_app=lambda *args, **kwargs: app)
def main():
    pass


class FlaskCommand(Command):

    def add_arguments(self, parser):
        # Capture command line help from Flask
        runner = click.testing.CliRunner()
        result = runner.invoke(main, ['--help'])
        flask_help = result.output.replace('main', 'gwcelery flask')

        group = parser.add_argument_group(
            'Flask Options', description=flask_help)
        group.add_argument(
            'flask_args', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

    def run(self, *args, flask_args=(), **kwargs):
        # Allow port number to be specified from an environment variable.
        port = os.environ.get('FLASK_PORT')
        if port:
            flask_args += ['--port', port]
        main(flask_args)


main.__doc__ = FlaskCommand.__doc__ = __doc__
