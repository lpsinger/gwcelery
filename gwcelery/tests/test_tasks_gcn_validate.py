import json

import pkg_resources
import pytest

from ..tasks.gcn.validate import validate_voevent


@pytest.fixture
def fake_gcn(celeryconf, monkeypatch):

    def mock_download(filename, graceid):
        assert filename == 'G298048-1-Initial.xml'
        assert graceid == 'G298048'
        return pkg_resources.resource_string(__name__, 'data/' + filename)

    def mock_get_log(graceid):
        assert graceid == 'G298048'
        return json.loads(
            pkg_resources.resource_string(__name__, 'data/G298048_log.json'))

    def mock_create_tag(filename, tag, graceid):
        assert filename == 'G298048-1-Initial.xml'
        assert tag == 'gcn_received'
        assert graceid == 'G298048'

    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.download', mock_download)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.get_log', mock_get_log)
    monkeypatch.setattr(
        'gwcelery.tasks.gracedb.create_tag', mock_create_tag)

    # Get the VOEvent.
    yield pkg_resources.resource_string(
        __name__, 'data/G298048-1-Initial.xml')


def test_validate_voevent(fake_gcn):
    """Test that the fake GCN notice matches what we actually sent."""
    validate_voevent(fake_gcn)


def test_validate_voevent_mismatched_param(fake_gcn):
    """Test that we correctly detect mismatched parameter values in GCNs."""
    with pytest.raises(AssertionError, match="^GCN does not match GraceDb$"):
        validate_voevent(fake_gcn + b'\n')
