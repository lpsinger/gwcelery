"""Package data helpers."""
from importlib import resources
import json
import pickle

__all__ = ('read_json', 'read_pickle')


def read_json(*args, **kwargs):
    """Load a JSON file from package data."""
    with resources.open_text(*args, **kwargs) as f:
        return json.load(f)


def read_pickle(*args, **kwargs):
    """Load a JSON file from package data."""
    with resources.open_binary(*args, **kwargs) as f:
        return pickle.load(f)
