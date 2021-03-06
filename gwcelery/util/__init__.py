"""Miscellaneous utilities that are useful inside many different tasks."""
import os
import pkgutil

__all__ = ()

# Import all symbols from all submodules of this module.
for _, module, _ in pkgutil.iter_modules([os.path.dirname(__file__)]):
    exec('from . import {0};'
         '__all__ += getattr({0}, "__all__", ());'
         'from .{0} import *'.format(module))
    del module

# Clean up
del os, pkgutil
