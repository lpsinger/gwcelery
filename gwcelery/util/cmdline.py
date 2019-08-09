"""Utilities for calling command-line tools as Python functions."""
import contextlib

__all__ = ('handling_system_exit',)


@contextlib.contextmanager
def handling_system_exit():
    """Catch any :obj:`SystemExit` and re-raise it as :obj:`RuntimeError`.

    Some Celery tasks in this package call main functions of command-line tools
    from other packages. Those main functions may try to exit the Python
    interpreter (if, for example, the command-line arguments are not
    understood).

    Catch any :obj:`SystemExit` exception. If the exit code is zero (signifying
    a normal exit status), then ignore the exception. If the exit code is
    nonzero (signifying an error exit status), then re-raise it as a
    :obj:`RuntimeError` so that the error is reported but the Celery worker is
    not killed.
    """
    try:
        yield
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(
                'Command-line tool tried to exit with nonzero status') from e
