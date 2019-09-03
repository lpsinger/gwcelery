import json

import pytest

from ..tasks import em_bright


def test_classify_gstlal():
    res = json.loads(em_bright.classifier_gstlal(
        (1.355607, 1.279483, 0.0, 0.0, 15.6178), 'G211117'))
    assert res['HasNS'] == pytest.approx(1.0, abs=1e-3)
    assert res['HasRemnant'] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize(
    'args,graceid,has_ns,has_remnant',
    [[(1.355607, 1.279483, 0.0, 0.0, 15.6178), 'G21117', 1.0, 1.0],
     [(40.0, 3.0001, 0.0, 0.0, 15), 'G21117', 0.0, 0.0],
     [(40.0, 2.9999, 0.0, 0.0, 15), 'G21117', 1.0, 0.0]])
def test_classify_other(args, graceid, has_ns, has_remnant):
    res = json.loads(em_bright.classifier_other(args, graceid))
    assert res['HasNS'] == has_ns
    assert res['HasRemnant'] == has_remnant
