"""
Sphinx gets confused by :class:`celery.local.PromiseProxy` objects.
If running under Sphinx, substitute a dummy class for
:class:`~celery.local.PromiseProxy`.
"""
from .sphinx import SPHINX

__all__ = ('PromiseProxy',)

if SPHINX:  # pragma: no cover
    class PromiseProxy:

        def __init__(self, *args, **kwargs):
            pass
else:
    from celery.local import PromiseProxy
