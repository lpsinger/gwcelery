"""Package data helpers."""
import json

import pkg_resources

__all__ = ('resource_json',)


def resource_json(*args, **kwargs):
    """Load a JSON file from package data."""
    with pkg_resources.resource_stream(*args, **kwargs) as f:
        return json.load(f)
