import json

import pkg_resources


def resource_json(*args, **kwargs):
    with pkg_resources.resource_stream(*args, **kwargs) as f:
        return json.load(f)
