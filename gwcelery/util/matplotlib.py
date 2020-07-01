"""Matplotlib environment management."""
from contextlib import contextmanager

from matplotlib import pyplot as plt

__all__ = ('closing_figures',)


@contextmanager
def closing_figures():
    """Close figure that are created in a with: statement."""
    old_fignums = set(plt.get_fignums())
    try:
        yield
    finally:
        new_fignums = set(plt.get_fignums())
        for fignum in new_fignums - old_fignums:
            plt.close(fignum)
