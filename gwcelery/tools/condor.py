"""Shortcuts for HTCondor commands to manage deployment of GWCelery on LIGO
Data Grid clusters.

These commands apply to the GWCelery instance that is
running in the current working directory.
"""
from importlib import resources
import json
import os
import shlex
import subprocess
import sys
import time

from celery.bin.base import Command
import lxml.etree

from .. import data

with resources.path(data, 'gwcelery.sub') as p:
    SUBMIT_FILE = str(p)


def get_constraints():
    return '-constraint', 'JobBatchName=={} && Iwd=={}'.format(
        json.dumps('gwcelery'),  # JSON string literal escape sequences
        json.dumps(os.getcwd())  # are a close match to HTCondor ClassAds.
    )


def run_exec(*args):
    print(' '.join(shlex.quote(arg) for arg in args))
    os.execvp(args[0], args)


def running():
    """Determine if GWCelery is already running under HTCondor."""
    status = subprocess.check_output(('condor_q', '-xml', *get_constraints()))
    classads = lxml.etree.fromstring(status)
    return classads.find('.//c') is not None


def submit(app):
    """Submit all GWCelery jobs to HTCondor (if not already running)."""
    if running():
        print('error: GWCelery jobs are already running in this directory.\n'
              'First remove existing jobs with "gwcelery condor rm".\n'
              'To see the status of those jobs, run "gwcelery condor q".',
              file=sys.stderr)
        sys.exit(1)
    else:
        accounting_group = app.conf['condor_accounting_group']
        run_exec('condor_submit',
                 'accounting_group={}'.format(accounting_group),
                 SUBMIT_FILE)


def resubmit(app):
    """Remove any running GWCelery jobs and resubmit to HTCondor."""
    if running():
        subprocess.check_call(('condor_rm', *get_constraints()))
    timeout = 120
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not running():
            break
        time.sleep(1)
    else:
        print('error: Could not stop all GWCelery jobs', file=sys.stderr)
        sys.exit(1)
    accounting_group = app.conf['condor_accounting_group']
    run_exec('condor_submit', 'accounting_group={}'.format(accounting_group),
             SUBMIT_FILE)


def rm(app):
    """Remove all GWCelery jobs."""
    run_exec('condor_rm', *get_constraints())


def hold(app):
    """Put all GWCelery jobs on hold."""
    run_exec('condor_hold', *get_constraints())


def release(app):
    """Release all GWCelery jobs from hold status."""
    run_exec('condor_release', *get_constraints())


def q(app):
    """Show status of all GWCelery jobs."""
    run_exec('condor_q', '-nobatch', *get_constraints())


class CondorCommand(Command):

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers()
        for func in [submit, rm, hold, release, resubmit, q]:
            subparser = subparsers.add_parser(func.__name__, help=func.__doc__)
            subparser.set_defaults(func=func)

    def run(self, func=None, **kwargs):
        func(self.app)


CondorCommand.__doc__ = __doc__
