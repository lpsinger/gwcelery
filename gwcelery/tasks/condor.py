"""Submit and monitor HTCondor jobs [1]_.

Notes
-----
Internally, we use the XML condor log format [2]_ for easier parsing.

References
----------
.. [1] http://research.cs.wisc.edu/htcondor/manual/latest/condor_submit.html
.. [2] http://research.cs.wisc.edu/htcondor/classad/refman/node3.html

"""
from distutils.dir_util import mkpath
import os
import subprocess
import tempfile

import lxml.etree

from .. import app


def _escape_arg(arg):
    """Escape a command line argument for an HTCondor submit file."""
    arg = arg.replace('"', '""').replace("'", "''")
    if ' ' in arg or '\t' in arg:
        arg = "'" + arg + "'"
    return arg


def _escape_args(args):
    """Escape a list of command line arguments for an HTCondor submit file."""
    return '"' + ' '.join(_escape_arg(arg) for arg in args) + '"'


def _mklog(suffix):
    """Create a unique path for an HTCondor log."""
    condor_dir = os.path.expanduser('~/.cache/condor')
    mkpath(condor_dir)
    with tempfile.NamedTemporaryFile(dir=condor_dir, suffix=suffix) as f:
        return f.name


def _read(filename):
    with open(filename, 'r') as f:
        return f.read()


def _rm_f(*args):
    for arg in args:
        try:
            os.remove(arg)
        except OSError:
            pass


def _parse_classad(c):
    """Turn a ClassAd XML fragment into a dictionary of Python values.

    Note that this supports only the small subset of the ClassAd XML
    syntax [2]_ that we need to determine if a job succeeded or failed.
    """
    if c is not None:
        for a in c.findall('a'):
            key = a.attrib['n']
            child, = a.getchildren()
            if child.tag == 's':
                value = str(child.text)
            elif child.tag == 'b':
                value = (child.attrib['v'] == 't')
            elif child.tag == 'i':
                value = int(child.text)
            else:
                # Coverage skipped below because the Python compiler optimzies
                # away ``continue`` statements.
                #
                # See <https://bitbucket.org/ned/coveragepy/issues/198>.
                continue  # pragma: no cover
            yield key, value


def _read_last_event(log):
    """Get the last event from an HTCondor log file.

    FIXME: It would be more efficient in terms of I/O and file desciptors to
    use a single HTCondor log file for all jobs and use the inotify
    capabilities of ``htcondor.read_events`` to avoid unnecessary polling.
    """
    tree = lxml.etree.fromstring('<classads>' + _read(log) + '</classads>')
    return dict(_parse_classad(tree.find('c[last()]')))


def _submit(submit_file=None, **kwargs):
    args = ['condor_submit']
    for key, value in kwargs.items():
        args += ['-append', '{}={}'.format(key, value)]
    if submit_file is None:
        args += ['/dev/null', '-queue', '1']
    else:
        args += [submit_file]
    subprocess.run(args, capture_output=True, check=True)


class JobAborted(Exception):
    """Raised if an HTCondor job was aborted (e.g. by ``condor_rm``)."""


class JobRunning(Exception):
    """Raised if an HTCondor job is still running."""


class JobFailed(subprocess.CalledProcessError):
    """Raised if an HTCondor job fails."""


@app.task(bind=True, autoretry_for=(JobRunning,), default_retry_delay=1,
          ignore_result=True, max_retries=None, retry_backoff=True,
          shared=False)
def submit(self, submit_file, log=None):
    """Submit a job using HTCondor.

    Parameters
    ----------
    submit_file : str
        Path of the submit file.
    log: str
        Used internally to track job state. Caller should not set.

    Raises
    ------
    :class:`JobAborted`
        If the job was aborted (e.g. by running ``condor_rm``).
    :class:`JobFailed`
        If the job terminates and returns a nonzero exit code.
    :class:`JobRunning`
        If the job is still running. Causes the task to be re-queued until the
        job is complete.

    Example
    -------
    >>> submit.s('example.sub',
    ...          accounting_group='ligo.dev.o3.cbc.explore.test')

    """
    if log is None:
        log = _mklog('.log')
        try:
            _submit(submit_file, log_xml='true', log=log)
        except subprocess.CalledProcessError:
            _rm_f(log)
            raise
        self.retry((submit_file,), dict(log=log))
    else:
        event = _read_last_event(log)
        if event.get('MyType') == 'JobTerminatedEvent':
            _rm_f(log)
            if event['TerminatedNormally'] and event['ReturnValue'] != 0:
                raise JobFailed(event['ReturnValue'], (submit_file,))
        elif event.get('MyType') == 'JobAbortedEvent':
            _rm_f(log)
            raise JobAborted(event)
        else:
            raise JobRunning(event)


@app.task(bind=True, autoretry_for=(JobRunning,), default_retry_delay=1,
          max_retries=None, retry_backoff=True, shared=False)
def check_output(self, args, log=None, error=None, output=None, **kwargs):
    """Call a process using HTCondor.

    Call an external process using HTCondor, in a manner patterned after
    :meth:`subprocess.check_output`. If successful, returns its output on
    stdout. On failure, raise an exception.

    Parameters
    ----------
    args : list
        Command line arguments, as if passed to :func:`subprocess.check_call`.
    log, error, output : str
        Used internally to track job state. Caller should not set.
    **kwargs
        Extra submit description file commands. See the documentation for
        ``condor_submit`` for possible values.

    Returns
    -------
    str
        Captured output from command.

    Raises
    ------
    :class:`JobAborted`
        If the job was aborted (e.g. by running ``condor_rm``).
    :class:`JobFailed`
        If the job terminates and returns a nonzero exit code.
    :class:`JobRunning`
        If the job is still running. Causes the task to be re-queued until the
        job is complete.

    Example
    -------
    >>> check_output.s(['sleep', '10'],
    ...                accounting_group='ligo.dev.o3.cbc.explore.test')

    """
    # FIXME: Refactor to reuse common code from this task and
    # gwcelery.tasks.condor.submit.

    if log is None:
        log = _mklog('.log')
        error = _mklog('.err')
        output = _mklog('.out')
        kwargs = dict(kwargs,
                      universe='vanilla',
                      executable='/usr/bin/env',
                      getenv='true',
                      log_xml='true',
                      arguments=_escape_args(args),
                      log=log, error=error, output=output)
        try:
            _submit(**kwargs)
        except subprocess.CalledProcessError:
            _rm_f(log, error, output)
            raise
        self.retry((args,), kwargs)
    else:
        event = _read_last_event(log)
        if event.get('MyType') == 'JobTerminatedEvent':
            captured_error = _read(error)
            captured_output = _read(output)
            _rm_f(log, error, output)
            if event['TerminatedNormally'] and event['ReturnValue'] == 0:
                return captured_output
            else:
                raise JobFailed(event['ReturnValue'], args,
                                captured_output,
                                captured_error)
        elif event.get('MyType') == 'JobAbortedEvent':
            _rm_f(log, error, output)
            raise JobAborted(event)
        else:
            raise JobRunning(event)
