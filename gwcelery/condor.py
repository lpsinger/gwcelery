"""Provide subcommand to manage GWCelery through HTCondor."""
import os
import shlex
import subprocess
import sys
import time

from celery.bin.base import Command
import lxml.etree
import pkg_resources

SUBMIT_FILE = pkg_resources.resource_filename(__name__, 'data/gwcelery.sub')
CONSTRAINTS = ('-constraint', 'JobBatchName=="gwcelery"')


def run_exec(*args):
    print(' '.join(shlex.quote(arg) for arg in args))
    os.execvp(args[0], args)


def running():
    """Determine if GWCelery is already running under HTCondor."""
    status = subprocess.check_output(('condor_q', '-xml') + CONSTRAINTS)
    classads = lxml.etree.fromstring(status)
    return classads.find('.//c') is not None


def submit():
    """Submit all GWCelery jobs to HTCondor (if not already running)."""
    if running():
        print('error: GWCelery jobs are already running.\n'
              'You must first remove exist jobs with "gwcelery condor rm".\n'
              'To see the status of those jobs, run "gwcelery condor q".',
              file=sys.stderr)
        sys.exit(1)
    else:
        run_exec('condor_submit', SUBMIT_FILE)


def resubmit():
    """Remove any running GWCelery jobs and resubmit to HTCondor."""
    if running():
        subprocess.check_call(('condor_rm',) + CONSTRAINTS)
    timeout = 60
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not running():
            break
        time.sleep(1)
    else:
        print('error: Could not stop all GWCelery jobs', file=sys.stderr)
        sys.exit(1)
    run_exec('condor_submit', SUBMIT_FILE)


def rm():
    """Remove all GWCelery jobs."""
    run_exec('condor_rm', *CONSTRAINTS)


def hold():
    """Put all GWCelery jobs on hold."""
    run_exec('condor_hold', *CONSTRAINTS)


def release():
    """Release all GWCelery jobs from hold status."""
    run_exec('condor_release', *CONSTRAINTS)


def q():
    """Show status of all GWCelery jobs."""
    run_exec('condor_q', '-nobatch', *CONSTRAINTS)


class CondorCommand(Command):
    """Shortcuts for HTCondor commands to manage deployment of GWCelery on LIGO
    Data Grid clusters."""

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers()
        for func in [submit, rm, hold, release, resubmit, q]:
            subparser = subparsers.add_parser(func.__name__, help=func.__doc__)
            subparser.set_defaults(func=func)

    def run(self, func=None, **kwargs):
        func()
