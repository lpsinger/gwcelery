from contextlib import contextmanager
import tempfile

__all__ = ('NamedTemporaryFile',)


@contextmanager
def NamedTemporaryFile(content=None, **kwargs):  # noqa: N802
    r"""Convenience wrapper for :func:`tempfile.NamedTemporaryFile` that writes
    some data to the file before handing it to the calling code.

    Parameters
    ----------

    content : str, bytes, None
        Initial contents of the file.

    \**kwargs
        Additional keyword arguments to pass to
        :func:`tempfile.NamedTemporaryFile`.
    """
    if isinstance(content, bytes):
        kwargs = dict(kwargs, mode='w+b')
    elif isinstance(content, str):
        kwargs = dict(kwargs, mode='w+')
    elif content is not None:
        raise TypeError('content is of unknown type')
    with tempfile.NamedTemporaryFile(**kwargs) as f:
        if content is not None:
            f.write(content)
            f.flush()
            f.seek(0)
        yield f
