"""Flask web application views."""
import datetime
import re

from astropy.time import Time
from flask import flash, jsonify, redirect, render_template, request, url_for
from ligo.gracedb.rest import HTTPError as GraceDbHTTPError

from . import app as celery_app
from .flask import app, cache
from .tasks import first2years, gracedb, orchestrator


@app.route('/')
def index():
    return render_template('index.jinja2', conf=celery_app.conf)


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


@app.route('/typeahead_em_bright_filename')
@cache.cached(query_string=True)
def typeahead_em_bright_filename():
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
            'em_bright_filename', 'p_astro_filename')
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
