"""Package data helpers."""
from importlib import resources
import json
import pickle

from astropy.utils.data import get_readable_fileobj


__all__ = ('read_json', 'read_pickle')


def read_json(*args, **kwargs):
    """Load a JSON file from package data."""
    with resources.open_text(*args, **kwargs) as f:
        return json.load(f)


def read_pickle(*args, **kwargs):
    """Load a pickle file using astropy.utils.data."""
    with get_readable_fileobj(*args, **kwargs) as f:
        return pickle.load(f)
