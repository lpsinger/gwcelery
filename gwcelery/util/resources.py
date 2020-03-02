"""Package data helpers."""
import json
import pickle

import pkg_resources

__all__ = ('resource_json', 'resource_pickle')


def resource_json(*args, **kwargs):
    """Load a JSON file from package data."""
    with pkg_resources.resource_stream(*args, **kwargs) as f:
        return json.load(f)


def resource_pickle(*args, **kwargs):
    """Load a JSON file from package data."""
    with pkg_resources.resource_stream(*args, **kwargs) as f:
        return pickle.load(f)
