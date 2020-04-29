from importlib import resources
import logging
from unittest.mock import patch

from comet.utility.xml import xml_document
import lxml.etree
import pytest

from ..tasks import gcn
from . import data

logging.basicConfig(level=logging.INFO)


def fake_gcn(notice_type):
    # Check the real GCN notice, which is valid.
    payload = resources.read_binary(data, 'G298048-1-Initial.xml')
    root = lxml.etree.fromstring(payload)
    notice_type = str(int(notice_type))
    root.find(".//Param[@name='Packet_Type']").attrib['value'] = notice_type
    return xml_document(root)


def test_unrecognized_notice_type(caplog):
    """Test handling an unrecognized (enum not defined) notice type."""
    caplog.set_level(logging.WARNING)
    gcn.handler.dispatch(fake_gcn(10000))
    record, = caplog.records
    assert record.message == 'ignoring unrecognized key: 10000'


def test_unregistered_notice_type(caplog):
    """Test handling an unregistered notice type."""
    caplog.set_level(logging.WARNING)
    gcn.handler.dispatch(fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
    record, = caplog.records
    assert record.message == ('ignoring unrecognized key: '
                              '<NoticeType.SWIFT_UVOT_POS_NACK: 89>')


@pytest.fixture
def reset_handlers():
    old_handler = dict(gcn.handler)
    gcn.handler.clear()
    yield
    gcn.handler.update(old_handler)


def test_registered_notice_type(reset_handlers):
    @gcn.handler(gcn.NoticeType.AGILE_POINTDIR, gcn.NoticeType.AGILE_TRANS)
    def agile_handler(payload):
        pass

    with patch.object(agile_handler, 'run') as mock_run:
        gcn.handler.dispatch(fake_gcn(gcn.NoticeType.SWIFT_UVOT_POS_NACK))
        mock_run.assert_not_called()
        gcn.handler.dispatch(fake_gcn(gcn.NoticeType.AGILE_POINTDIR))
        mock_run.assert_called_once()
