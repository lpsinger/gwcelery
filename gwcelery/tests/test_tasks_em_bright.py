import json

import pytest

from ..tasks import em_bright


def test_classify_gstlal():
    res = json.loads(em_bright.classifier_gstlal(
        (1.355607, 1.279483, 0.0, 0.0, 15.6178), 'G211117'))
    assert res['HasNS'] == pytest.approx(1.0, abs=1e-3)
    assert res['HasRemnant'] == pytest.approx(1.0, abs=1e-3)


def test_classify_other():
    res = json.loads(em_bright.classifier_other(
        (1.355607, 1.279483, 0.0, 0.0, 15.6178), 'G211117'))
    assert res['HasNS'] == 1.0
    assert res['HasRemnant'] == 1.0
