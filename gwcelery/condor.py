"""Provide subcommand to manage GWCelery through HTCondor."""
import os
import shlex
import subprocess
import sys

from celery.bin.base import Command
import lxml.etree
import pkg_resources

SUBMIT_FILE = pkg_resources.resource_filename(__name__, 'data/gwcelery.sub')
CONSTRAINTS = ('-constraint', 'JobBatchName=="gwcelery"')


def run_exec(*args):
    print(' '.join(shlex.quote(arg) for arg in args))
    os.execvp(args[0], args)


def submit():
    """Submit all GWCelery jobs to HTCondor (if not already running)."""
    status = subprocess.check_output(('condor_q', '-xml') + CONSTRAINTS)
    classads = lxml.etree.fromstring(status)
    if classads.find('.//c') is None:
        run_exec('condor_submit', SUBMIT_FILE)
    else:
        print('error: GWCelery jobs are already running.\n'
              'You must first remove exist jobs with "gwcelery condor rm".\n'
              'To see the status of those jobs, run "gwcelery condor q".',
              file=sys.stderr)
        sys.exit(1)


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
        for func in [submit, rm, hold, release, q]:
            subparser = subparsers.add_parser(func.__name__, help=func.__doc__)
            subparser.set_defaults(func=func)

    def run(self, func=None, **kwargs):
        func()
