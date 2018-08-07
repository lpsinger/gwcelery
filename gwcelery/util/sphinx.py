"""
Detect if we are running under Sphinx.
"""
import os
import sys

__all__ = ('SPHINX',)

SPHINX = (os.path.basename(sys.argv[0]) == 'sphinx-build'
          or 'build_sphinx' in sys.argv)
