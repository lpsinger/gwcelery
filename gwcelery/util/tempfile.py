from __future__ import absolute_import
from contextlib import contextmanager
import tempfile
import shutil

import six

__all__ = ('NamedTemporaryFile', 'TemporaryDirectory')


@contextmanager
def NamedTemporaryFile(content=None, **kwargs):
    """Convenience wrapper for :func:`tempfile.NamedTemporaryFile` that writes
    some data to the file before handing it to the calling code.

    Parameters
    ----------

    content : str, bytes, None
        Initial contents of the file.

    \**kwargs
        Additional keyword arguments to pass to
        :func:`tempfile.NamedTemporaryFile`.
    """
    if isinstance(content, six.binary_type):
        kwargs = dict(kwargs, mode='w+b')
    elif isinstance(content, six.text_type):
        kwargs = dict(kwargs, mode='w+')
    elif content is not None:
        raise TypeError('content is of unknown type')
    with tempfile.NamedTemporaryFile(**kwargs) as f:
        if content is not None:
            f.write(content)
            f.flush()
            f.seek(0)
        yield f


@contextmanager
def TemporaryDirectory(suffix='', prefix='tmp', dir=None, delete=True):
    """Context manager for creating and cleaning up a temporary directory."""
    try:
        dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        yield dir
    finally:
        if delete:
            shutil.rmtree(dir)
