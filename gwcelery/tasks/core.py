"""Base classes for other Celery tasks."""
from operator import itemgetter

from celery import group
from celery.utils.log import get_logger

from .. import app

log = get_logger(__name__)


@app.task(shared=False)
def identity(arg):
    """Identity task (returns its input)."""
    return arg


@app.task(shared=False)
def _pack(result, i):
    return i, result


@app.task(shared=False)
def _unpack(results):
    return tuple(map(itemgetter(1), sorted(results, key=itemgetter(0))))


def ordered_group(*args):
    """Like :meth:`celery.group`, but preserve order.

    This is a temporary workaround for
    https://github.com/celery/celery/pull/4858."""
    return group(arg | _pack.s(i) for i, arg in enumerate(args)) | _unpack.s()


class DispatchHandler(dict):

    def process_args(self, *args, **kwargs):
        r"""Determine key and callback arguments.

        The default implementation treats the first positional argument as the
        key.

        Parameters
        ----------
        \*args
            Arguments passed to :meth:`__call__`.
        \*\*kwargs
            Keyword arguments passed to :meth:`__call__`.

        Returns
        -------
        key
            The key to determine which callback to invoke.
        \*args
            The arguments to pass to the registered callback.
        \*\*kwargs
            The keyword arguments to pass to the registered callback.
        """
        key, *args = args
        return key, args, kwargs

    def __call__(self, *keys, **kwargs):
        r"""Create a new task and register it as a callback for handling the
        given keys.

        Parameters
        ----------
        \*keys : list
            Keys to match
        \*\*kwargs
            Additional keyword arguments for `celery.Celery.task`.
        """

        def wrap(f):
            f = app.task(ignore_result=True, **kwargs)(f)
            for key in keys:
                self.setdefault(key, []).append(f)
            return f

        return wrap

    def dispatch(self, *args, **kwargs):
        log.debug('considering dispatch: args=%r, kwargs=%r', args, kwargs)
        try:
            key, args, kwargs = self.process_args(*args, **kwargs)
        except (TypeError, ValueError):
            log.exception('error unpacking key')
            return
        log.debug('unpacked: key=%r, args=%r, kwargs=%r', key, args, kwargs)

        try:
            matching_handlers = self[key]
        except KeyError:
            log.warning('ignoring unrecognized key: %r', key)
        else:
            log.info('calling handlers %r for key %r', matching_handlers, key)
            group([handler.s() for handler in matching_handlers]).apply_async(
                args, kwargs)
