import io
import json
from unittest.mock import patch
import urllib

import pkg_resources
import pytest

from ..tasks import em_bright


def test_classify_gstlal():
    class MockResponse(object):
        def read(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/test_classifier.pickle') as f:
                return f.read()

    with patch.object(urllib.request, 'urlopen', return_value=MockResponse()) \
            as mock_urlopen:
        res = json.loads(em_bright.classifier_gstlal((1.355607,
                                                      1.279483,
                                                      0.0,
                                                      0.0,
                                                      15.6178),
                                                     'G211117'))
    mock_urlopen.assert_called_once()
    assert res['HasNS'] == pytest.approx(1.0, abs=1e-3)
    assert res['HasRemnant'] == pytest.approx(1.0, abs=1e-3)


def test_classify_other():
    res = json.loads(em_bright.classifier_other((1.355607,
                                                 1.279483,
                                                 0.0,
                                                 0.0,
                                                 15.6178),
                                                'G211117'))
    assert res['HasNS'] == 1.0
    assert res['HasRemnant'] == 1.0


def test_unpickling_error():
    class BadResponse(object):
        def read(self):
            return io.BytesIO(b'Invalid Pickle').read()

    # function should run with default classifier with package data
    with patch.object(urllib.request, 'urlopen', return_value=BadResponse()):
        res = json.loads(em_bright.classifier_gstlal((1.355607,
                                                      1.279483,
                                                      0.0,
                                                      0.0,
                                                      15.6178),
                                                     'G211117'))
    assert res['HasNS'] == pytest.approx(1.0, abs=1e-3)
    assert res['HasRemnant'] == pytest.approx(1.0, abs=1e-3)
