"""
Sphinx gets confused by :class:`celery.local.PromiseProxy` objects.
If running under Sphinx, substitute a dummy class for
:class:`~celery.local.PromiseProxy`.
"""
import os
import sys

__all__ = ('PromiseProxy',)

prog = os.path.basename(sys.argv[0])
if prog != 'sphinx-build' and 'build_sphinx' not in sys.argv:
    from celery.local import PromiseProxy
else:
    class PromiseProxy:

        def __init__(self, *args, **kwargs):
            pass
