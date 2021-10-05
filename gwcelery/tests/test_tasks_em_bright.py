import json
from unittest.mock import patch

import h5py
import numpy as np
import pytest

from ..tasks import em_bright
from ..util.tempfile import NamedTemporaryFile


@patch('gwcelery.tasks.gracedb.download.run', return_value='mock_em_bright')
@patch('gwcelery.tasks.gracedb.upload.run')
@patch('gwcelery.tasks.em_bright.plot.run')
def test_handle_em_bright_json(mock_plot, mock_upload, mock_download):
    alert = {
        "data": {
            "tag_names": ["em_bright"],
            "filename": "em_bright.json"
        },
        "uid": "TS123456",
        "alert_type": "log"
    }
    em_bright.handle(alert)
    mock_download.assert_called_once_with(
        'em_bright.json',
        'TS123456'
    )
    mock_plot.assert_called_once_with('mock_em_bright')
    mock_upload.assert_called_once()


def test_classify_gstlal():
    res = json.loads(em_bright.classifier_gstlal(
        1.355607, 1.279483, 0.0, 0.0, 15.6178))
    assert res['HasNS'] == pytest.approx(1.0, abs=1e-3)
    assert res['HasRemnant'] == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize(
        'posterior_samples,embright',
        [[[(1.2, 1.0, 0.0, 0.0, 100.0, 0.0, 0.0),
           (2.0, 0.5, 0.99, 0.99, 150.0, 0.0, 0.0)],
          {'HasNS': 1.0, 'HasRemnant': 1.0}],
         [[(20., 12.0, 0.0, 0.0, 200.0, 0.0, 0.0),
           (22.0, 11.5, 0.80, 0.00, 250.0, 0.0, 0.0),
           (21.0, 10.0, 0.0, 0.0, 250, 0.0, 0.0)],
          {'HasNS': 0.0, 'HasRemnant': 0.0}]])
def test_posterior_samples(posterior_samples, embright):
    with NamedTemporaryFile() as f:
        filename = f.name
        with h5py.File(f, 'r+') as tmp_h5:
            data = np.array(
                    posterior_samples,
                    dtype=[('mc', '<f8'), ('q', '<f8'),
                           ('a1', '<f8'), ('a2', '<f8'),
                           ('dist', '<f8'), ('tilt1', '<f8'),
                           ('tilt2', '<f8')])
            tmp_h5.create_dataset(
                'lalinference/lalinference_mcmc/posterior_samples',
                data=data)
        content = open(filename, 'rb').read()
    r = json.loads(em_bright.em_bright_posterior_samples(content))
    assert r == embright


@pytest.mark.parametrize(
    'args,has_ns,has_remnant',
    [[(1.355607, 1.279483, 0.0, 0.0, 15.6178), 1.0, 1.0],
     [(40.0, 3.0001, 0.0, 0.0, 15), 0.0, 0.0],
     [(40.0, 2.9999, 0.0, 0.0, 15), 1.0, 0.0]])
def test_classify_other(args, has_ns, has_remnant):
    res = json.loads(em_bright.classifier_other(*args))
    assert res['HasNS'] == has_ns
    assert res['HasRemnant'] == has_remnant
