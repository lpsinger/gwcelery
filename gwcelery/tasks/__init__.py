"""All Celery tasks are declared in submodules of this module."""
from __future__ import absolute_import
import importlib
import os
import pkgutil

# Import all submodules of this module
modules = vars()
for _, module, _ in pkgutil.iter_modules([os.path.dirname(__file__)]):
    modules[module] = importlib.import_module('.' + module, __name__)

# Clean up
del importlib, module, modules, os, pkgutil
