from __future__ import absolute_import
from contextlib import contextmanager
import tempfile

import six

__all__ = ('NamedTemporaryFile',)


@contextmanager
def NamedTemporaryFile(**kwargs):
    """Convenience wrapper for NamedTemporaryFile that writes some data to
    the file before handing it to the calling code."""
    # Make a copy so that we don't modify kwargs
    kwargs = dict(kwargs)

    content = kwargs.pop('content', None)
    if isinstance(content, six.binary_type):
        kwargs['mode'] = 'w+b'
    elif isinstance(content, six.text_type):
        kwargs['mode'] = 'w+'
    elif content is not None:
        raise TypeError('content is of unknown type')
    with tempfile.NamedTemporaryFile(**kwargs) as f:
        if content is not None:
            f.write(content)
            f.flush()
            f.seek(0)
        yield f
