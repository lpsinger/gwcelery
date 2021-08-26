from importlib import resources
from unittest.mock import patch

import pytest

from ..tasks.gcn import validate
from ..util import read_json
from . import data


@pytest.fixture
def fake_gcn(monkeypatch):

    def mock_download(filename, graceid):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        return resources.read_binary(data, filename)

    def mock_get_log(graceid):
        assert graceid == 'G298048'
        return read_json(data, 'G298048_log.json')

    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.download', mock_download)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.get_log', mock_get_log)

    # Get the VOEvent.
    yield resources.read_binary(data, 'G298048-1-Initial.xml')


@patch('gwcelery.tasks.gracedb.create_tag.run')
@patch('gwcelery.tasks.gracedb.upload.run')
def test_validate_voevent(mock_upload, mock_create_tag, fake_gcn):
    """Test that the fake GCN notice matches what we actually sent."""
    validate(fake_gcn)
    mock_create_tag.assert_called_once_with(
        'G298048-1-Initial.xml', 'gcn_received', 'G298048')
    mock_upload.assert_not_called()


@patch('gwcelery.tasks.gracedb.create_tag.run')
@patch('gwcelery.tasks.gracedb.upload.run')
def test_validate_voevent_mismatched_param(
        mock_upload, mock_create_tag, fake_gcn):
    """Test that we correctly detect mismatched parameter values in GCNs."""
    with pytest.raises(
            ValueError,
            match="^VOEvent received from GCN differs from what we sent"):
        validate(fake_gcn + b'\n')
    mock_create_tag.assert_not_called()
    mock_upload.assert_called_once()
