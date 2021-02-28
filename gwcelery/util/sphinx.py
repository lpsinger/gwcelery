"""Detect if we are running under Sphinx."""
__all__ = ('SPHINX',)


try:
    # This global builtin variable is set in doc/conf.py.
    # See https://stackoverflow.com/a/65147676/167694
    SPHINX = __sphinx_build__
except NameError:
    SPHINX = False
