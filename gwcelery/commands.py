# Standard library imports
from __future__ import print_function
import argparse
import logging
import os
import pkg_resources
import subprocess
import sys

# Internal imports
from .tasks import dispatch


# Logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def lvalert_listen():
    """Start lvalert_listen, and restart if it dies."""
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', default='lvalert.cgca.uwm.edu',
                        help='LVAlert server [default: %(default)s]')
    args = parser.parse_args()

    # Locate .ini file for lvalert_listen
    inifile = pkg_resources.resource_filename(__name__, 'lvalert.ini')

    # Start lvalert_listen, and restart it if it dies
    while True:
        try:
            args = ['lvalert_listen', '-c', inifile, '-s', args.server]
            log.info('starting: %s', ' '.join(args))
            subprocess.check_call(args)
        except subprocess.CalledProcessError:
            log.exception('lvalert_listen died')
            pass


def lvalert_answer():
    """Ingest an lvalert payload in the task queue."""
    payload = sys.stdin.read()
    log.info('dispatching LVAlert payload: %s', payload)
    dispatch.delay(payload)


def worker():
    """Start up celery worker with some default arguments."""
    os.execlp('celery',
              'celery', 'worker', '-A', 'gwcelery.tasks', '--loglevel=info')
