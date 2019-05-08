import json
import logging
import os
import stat
from unittest.mock import patch

import lxml
import pkg_resources
import pytest

from ..tasks import lvalert


@pytest.fixture
def netrc_lvalert(tmpdir):
    path = str(tmpdir / 'netrc')
    with open(path, 'w') as f:
        os.fchmod(f.fileno(), stat.S_IRWXU)
        print('machine', 'lvalert.invalid', file=f)
        print('login', 'albert.einstein', file=f)
        print('password', 'foobar', file=f)
    with patch.dict(os.environ, NETRC=path):
        yield


@patch('sleek_lvalert.LVAlertClient')
@patch('gwcelery.tasks.lvalert.listen.is_aborted', side_effect=[False, True])
def test_listen(mock_is_aborted, mock_client, netrc_lvalert):
    client_instance = mock_client.return_value
    client_instance.get_subscriptions.return_value = ['superevent']

    # Run function under test
    lvalert.listen()

    mock_client.assert_called_once()
    client_instance.connect.assert_called_once_with()
    client_instance.process.assert_called_once_with(block=False)
    client_instance.subscribe.assert_called_once()
    # In our test scenario, we were already subscribed to 'superevent',
    # but not to 'cbc_gstlal'.
    assert 'superevent' not in client_instance.subscribe.call_args[0]
    assert 'cbc_gstlal' in client_instance.subscribe.call_args[0]
    client_instance.listen.assert_called_once_with(lvalert.handler.dispatch)
    client_instance.abort.assert_called_once_with()


@pytest.fixture
def fake_lvalert():
    with pkg_resources.resource_stream(__name__, 'data/lvalert_xmpp.xml') as f:
        root = lxml.etree.parse(f)
    node = root.find('.//{*}items').attrib['node']
    payload = root.find('.//{*}entry').text
    return node, payload


@patch(
    'gwcelery.tasks.gracedb.get_event.run',
    return_value={'graceid': 'T250822', 'group': 'CBC', 'pipeline': 'gstlal',
                  'far': 1e-7,
                  'extra_attributes':
                      {'CoincInspiral': {'snr': 10.},
                       'SingleInspiral': [{'mass1': 10., 'mass2': 5.}]}})
@patch('gwcelery.tasks.superevents.handle.run')
def test_handle_messages(mock_superevents_handle, mock_get_event,
                         netrc_lvalert, fake_lvalert):
    """Test handling an LVAlert message that originates from the configured
    GraceDB server."""
    node, payload = fake_lvalert

    # Manipulate alert content
    alert = json.loads(payload)
    alert['object']['self'] = \
        alert['object']['self'].replace('gracedb.ligo.org', 'gracedb.invalid')
    payload = json.dumps(alert)

    # Run function under test
    lvalert.handler.dispatch(node, payload)
    mock_superevents_handle.assert_called_once()


@patch('gwcelery.tasks.superevents.handle.run')
def test_handle_messages_wrong_server(mock_superevents_handle,
                                      netrc_lvalert, fake_lvalert, caplog):
    """Test handling an LVAlert message that originates from a GraceDB server
    other than the configured GraceDB server. It should be ignored."""
    node, payload = fake_lvalert

    # Manipulate alert content
    alert = json.loads(payload)
    alert['object']['self'] = \
        alert['object']['self'].replace('gracedb.ligo.org', 'gracedb2.invalid')
    payload = json.dumps(alert)

    # Run function under test
    caplog.set_level(logging.WARNING)
    lvalert.handler.dispatch(node, payload)
    record, *_ = caplog.records
    assert record.message == ('ignoring LVAlert message because it is '
                              'intended for GraceDB server '
                              'https://gracedb2.invalid/api/, but we are set '
                              'up for server https://gracedb.invalid/api/')
    mock_superevents_handle.assert_not_called()


@patch('gwcelery.tasks.superevents.handle.run')
def test_handle_messages_no_self_link(mock_superevents_handle,
                                      netrc_lvalert, fake_lvalert, caplog):
    """Test handling an LVAlert message that does not identify the GraceDB
    server of origin. It should be rejected."""
    node, payload = fake_lvalert

    # Manipulate alert content
    alert = json.loads(payload)
    del alert['object']['self']
    payload = json.dumps(alert)

    # Run function under test
    caplog.set_level(logging.ERROR)
    lvalert.handler.dispatch(node, payload)
    record, = caplog.records
    assert 'LVAlert message does not contain an API URL' in record.message
    mock_superevents_handle.assert_not_called()
