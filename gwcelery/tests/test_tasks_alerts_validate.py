import fastavro
import json
from importlib import resources
from unittest.mock import Mock, patch
from astropy.utils.data import download_files_in_parallel
import pytest

from .. import app
from ..tasks import alerts
from . import data


@pytest.fixture
def parsed_schema(socket_enabled):
    # NOTE cache=True won't check for updates, but cache='update' will return
    # an error if the URL is down. User will need to clear the cache to force a
    # new download when schema are updated.
    downloaded_schema = download_files_in_parallel([
        'https://git.ligo.org/emfollow/userguide/-/raw/main/_static/'
        'igwn.alerts.v1_0.ExternalCoincInfo.avsc',
        'https://git.ligo.org/emfollow/userguide/-/raw/main/_static/'
        'igwn.alerts.v1_0.EventInfo.avsc',
        'https://git.ligo.org/emfollow/userguide/-/raw/main/_static/'
        'igwn.alerts.v1_0.AlertType.avsc',
        'https://git.ligo.org/emfollow/userguide/-/raw/main/_static/'
        'igwn.alerts.v1_0.Alert.avsc'],
        cache=True,
        pkgname='lvk-userguide',
        show_progress=False
    )
    # Load the schema, the order does not matter other than the Alert schema
    # must be loaded last because it references the other schema. All of the
    # schema are saved in named_schemas, but we only need to save a reference
    # to the the Alert schema to write the packet. We overwrite the schema
    # variable each time to avoid the schema being printed to stdout.
    # NOTE Specifying expand=True when calling parse_schema is okay when only
    # one schema contains references to other schema, in our case only the
    # alerts schema contains references to other schema. More complicated
    # relationships between schema though can lead to behavior that does not
    # conform to the avro spec, and a different method will need to be used to
    # load the schema. See https://github.com/fastavro/fastavro/issues/624 for
    # more info.
    named_schemas = {}
    for s in downloaded_schema:
        with open(s, 'r') as f:
            schema = fastavro.schema.parse_schema(
                           json.load(f), named_schemas, expand=True)
    return schema


@patch('gwcelery.tasks.gracedb.download._orig_run',
       return_value=resources.read_binary(
           data,
           'MS220722v_bayestar.multiorder.fits'
       ))
def test_validate_alert(mock_download, parsed_schema, monkeypatch):
    """Validate public alerts against the schema from the userguide.
    """

    def _validate_alert(public_alert_avro_blob):
        assert len(public_alert_avro_blob.content) == 1
        fastavro.validation.validate(public_alert_avro_blob.content[0],
                                     parsed_schema, strict=True)

    # Replace the stream object with a mock object with _validiate_alert as its
    # write attribute
    mock_stream = Mock()
    mock_stream_write = Mock(side_effect=_validate_alert)
    mock_stream.write = mock_stream_write
    monkeypatch.setitem(app.conf, 'kafka_streams', {'scimma': mock_stream})

    # Load superevent dictionary, and embright/pastro json tuple
    superevent = json.loads(resources.read_binary(data, 'MS220722v.xml'))

    # Test preliminary, initial, and update alerts. All three are generated
    # using the same code path, so we only need to test 1
    alerts.download_skymap_and_send_alert(
        (
            '{"HasNS": 1.0, "HasRemnant": 1.0}',
            '{"BNS": 0.9999976592278448, "NSBH": 0.0, "BBH": 0.0,'
            '"Terrestrial": 2.3407721552252815e-06}'
        ),
        superevent,
        'initial',
        'MS220722v_bayestar.multiorder.fits'
    ).delay()
    mock_download.assert_called_once()
    mock_stream_write.assert_called_once()

    # Reset mocks
    mock_stream_write.reset_mock()
    mock_download.reset_mock(return_value=True)

    # Test retraction alerts.
    alerts.send(None, superevent, 'retraction', None)
    mock_download.assert_not_called()
    mock_stream_write.assert_called_once()
