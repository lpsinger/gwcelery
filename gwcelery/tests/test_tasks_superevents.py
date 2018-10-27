import json
import pytest
from unittest.mock import patch

from ..tasks import gracedb, superevents
from . import resource_json

lvalert_content = json.loads(
    '''{
    "object":
        {
            "graceid": "",
            "gpstime": "",
            "pipeline": "",
            "group": "",
            "created": "",
            "far": "",
            "instruments": "",
            "labels": {},
            "extra_attributes":{},
            "submitter": "deep.chatterjee@ligo.org",
            "offline": false
        },
    "alert_type": "new",
    "uid": ""
    }'''
)


class T0212TTPResponse(object):
    def json(self):
        return resource_json(__name__, 'data/T0212_S0039_preferred.json')


class SingleT0212TTPResponse(object):
    def __init__(self, event):
        if event != 'T0212':
            raise ValueError("Called with incorrect preferred event")

    def json(self):
        response = resource_json(
            __name__, 'data/T0212_S0039_preferred.json')
        response['instruments'] = "H1"
        return response


class G000012TTPResponse(object):
    def json(self):
        return resource_json(__name__, 'data/G000012_S0040_preferred.json')


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    class FakeDb(object):
        def __init__(self):
            self._service_url = 'service_url'

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            elif gid == "G000012":
                return G000012TTPResponse()
            else:
                raise ValueError("Called with incorrect preferred event")
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    yield


def test_update_preferred_event(mock_db):
    def mock_response():
        return dict(graceid="T1234",
                    instruments="I1,J1,K1,L1,M1",
                    group="CBC",
                    superevent="some_superevent",
                    far=1e-30,
                    snr=30.0)
    with patch.object(gracedb.client, 'updateSuperevent') as p:
        superevents._update_superevent('S0039',
                                       'T0212',
                                       mock_response(),
                                       None,
                                       None)
        p.assert_called_with('S0039', preferred_event='T1234',
                             t_start=None, t_end=None, t_0=None)


def _mock_superevents(*args, **kwargs):
    return [
        {
            "superevent_id": "S123456",
            "preferred_event": "G000002",
            "t_start": 99.0,
            "t_0": 100.0,
            "gw_events": [
                "G000002",
            ],
            "t_end": 101.0
        }
    ]


def _mock_event(event):
    if event == "G000002":
        return {
            "graceid": "G000002",
            "gpstime": 100.0,
            "pipeline": "gstlal",
            "group": "CBC",
            "far": 1.e-31,
            "instruments": "H1,L1",
            "extra_attributes": {
                "CoincInspiral": {"snr": 20}
            },
            "offline": False
        }


@patch('gwcelery.tasks.gracedb.get_superevents', _mock_superevents)
@patch('gwcelery.tasks.gracedb.get_event', _mock_event)
def test_upload_same_event():
    """New event uploaded with the same coinc file as an
    existing event G000002. This could happen during testing
    the superevent manager.
    """
    # payload same as _mock_event except graceid
    payload = {
        "uid": "G000003",
        "alert_type": "new",
        "description": "",
        "object": {
            "graceid": "G000003",
            "gpstime": 100.0,
            "pipeline": "gstlal",
            "group": "CBC",
            "far": 1.e-31,
            "instruments": "H1,L1",
            "extra_attributes": {
                "CoincInspiral": {"snr": 20}
            },
            "offline": False
        }
    }
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()


def test_parse_trigger_raising():
    garbage_payload = dict(some_value=999, something_else=99)
    with pytest.raises(KeyError):
        superevents.handle(garbage_payload)


def test_parse_trigger_cbc_1(mock_db):
    """New trigger G000000, less significant than already
    existing superevent. Superevent window much larger than event
    window of G000000"""
    # New trigger G000000 time falls in S0039 window
    # addEventToSuperevent should be called
    # updateSuperevent should not be updated
    payload = dict(lvalert_content,
                   object={'graceid': 'G000000',
                           'gpstime': 1163905224.4332082,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3e-09,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'CoincInspiral': {'snr': 10.0}}},
                   alert_type='new',
                   uid='G000000')
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()


def test_parse_trigger_cbc_2(mock_db):
    """New trigger G000003, more significant than already
    existing superevent. Superevent window is much larger that
    event window of G000000"""
    payload = dict(lvalert_content,
                   object={'graceid': 'G000003',
                           'gpstime': 1163905224.4332082,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3e-31,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'CoincInspiral': {'snr': 30.0}}},
                   alert_type='new',
                   uid='G000003')
    # addEventToSuperevent should be called
    # preferred event should be updated
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', preferred_event='G000003',
                                   t_0=None, t_start=None, t_end=None)


def test_parse_trigger_cbc_3(mock_db):
    """New trigger G000001, not present among superevents
    New superevent created"""
    payload = dict(lvalert_content,
                   object={'graceid': 'G000001',
                           'gpstime': 1286741861.52678,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3e-31,
                           'instruments': 'H1,L1,V1',
                           'extra_attributes': {
                               'CoincInspiral': {'snr': 12.0}}},
                   alert_type='new',
                   uid='G000001')
    # G000001 absent in any superevent window, new superevent created
    # createSuperevent should be called exactly once
    with patch.object(gracedb.client, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once()


def test_parse_trigger_cbc_4(mock_db):
    """New trigger G000002, doesn't pass far threshold"""
    payload = dict(lvalert_content,
                   object={'graceid': 'G000002',
                           'gpstime': 1286741861.52678,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 5.5e-02,
                           'instruments': 'H1,L1,V1',
                           'extra_attributes': {
                               'CoincInspiral': {'snr': 4.0}}},
                   alert_type='new',
                   uid='G000002')
    superevents.handle(payload)
    # neither method is called due to low far
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'createSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_not_called()
        p2.assert_not_called()


def test_parse_trigger_burst_1(mock_db):
    """New cwb trigger G000005 with gpstime lying partially in
    S0039 window, not more significant than existing preferred
    event, superevent window changed.
    """
    payload = dict(lvalert_content,
                   object={'graceid': 'G000005',
                           'gpstime': 1163905214.4,
                           'group': 'Burst',
                           'pipeline': 'cwb',
                           'far': 3.02e-09,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'MultiBurst': {
                                   'duration': 0.23639,
                                   'start_time': 1163905215,
                                   'snr': 10.3440}}},
                   alert_type='new',
                   uid='G000005')
    # preferred event should not be updated
    # superevent window should change
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', preferred_event=None, t_0=None,
                                   t_end=pytest.approx(1163905239, abs=1),
                                   t_start=pytest.approx(1163905214, abs=1))


def test_parse_trigger_burst_2(mock_db):
    """New oLIB trigger G000006 with gpstime lying partially in
    S0039 window, more significant than already existing preferred
    event. superevent window changed
    """
    # preferred event not be updated, in spite of lower far of new event
    # because existing preferred event is CBC
    payload = dict(lvalert_content,
                   object={'graceid': 'G000006',
                           'gpstime': 1163905239.5,
                           'group': 'Burst',
                           'pipeline': 'oLIB',
                           'far': 3.02e-16,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'LalInferenceBurst': {
                                   'quality_mean': 20.6458,
                                   'frequency_mean': 117.9644,
                                   'omicron_snr_network': 8.77}}},
                   alert_type='new',
                   uid='G000006')
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', t_0=None, preferred_event=None,
                                   t_end=pytest.approx(1163905239, abs=1),
                                   t_start=pytest.approx(1163905214, abs=1))


def test_parse_trigger_burst_3(mock_db):
    """New oLIB trigger G000007, not present among superevents
    New superevent created.
    Q_mean = frequency_mean = 100., hence d_t_start = d_t_end = 1s
    """
    payload = dict(lvalert_content,
                   object={'graceid': 'G000007',
                           'gpstime': 1163905249.5,
                           'group': 'Burst',
                           'pipeline': 'oLIB',
                           'far': 3.02e-16,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'LalInferenceBurst': {
                                   'quality_mean': 100.0,
                                   'frequency_mean': 100.0,
                                   'omicron_snr_network': 8.0}}},
                   alert_type='new',
                   uid='G000007')
    # G000007 absent in any superevent window, new superevent created
    with patch.object(gracedb.client, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once_with(pytest.approx(1163905248.5),
                                  pytest.approx(1163905249.5),
                                  pytest.approx(1163905250.5),
                                  preferred_event='G000007',
                                  category='production')


def test_parse_trigger_burst_4(mock_db):
    """New CWB trigger G000008, not present among superevents
    New superevent created.
    extra attribute duration = 0.02s
    """
    payload = dict(lvalert_content,
                   object={'graceid': 'G000008',
                           'gpstime': 1128658942.9878,
                           'group': 'Burst',
                           'pipeline': 'CWB',
                           'far': 1.23e-09,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'MultiBurst': {
                                   'duration': 0.02,
                                   'start_time': 1128658942,
                                   'snr': 19.824}}},
                   alert_type='new',
                   uid='G000008')
    # G000008 absent in any superevent window, new superevent created
    with patch.object(gracedb.client, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once()


def test_single_ifo_1(mock_db):
    """New single IFO trigger G000009 same event attributes as
    G000000 (except single IFO). Will be added to superevent"""
    payload = dict(lvalert_content,
                   object={'graceid': 'G000009',
                           'gpstime': 1163905224.4332,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3.02e-09,
                           'instruments': 'H1',
                           'extra_attributes': {
                               'CoincInspiral': {
                                   'snr': 10.0}}},
                   alert_type='new',
                   uid='G000009')
    # New trigger G000009 time falls in S0039 window
    # addEventToSuperevent should be called
    # updateSuperevent should not be updated
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()


def test_single_ifo_2(mock_db):
    """New single IFO trigger G000010 same event attributed as G000003
    (except single IFO). More significant than existing superevent, but
    preferred event not changed
    """
    # New trigger G000010 falls in S0039 window
    payload = dict(lvalert_content,
                   object={'graceid': 'G000010',
                           'gpstime': 1163905224.4332,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3.02e-31,
                           'instruments': 'H1',
                           'extra_attributes': {
                               'CoincInspiral': {
                                   'snr': 30.0}}},
                   alert_type='new',
                   uid='G000010')
    # addEventToSuperevent should be called
    # preferred event should not be updated
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()


def test_single_ifo_3(mock_db):
    """New multi-IFO trigger CBC trigger G000011. Existing
    preferred event is a single IFO. Preferred event
    updated with G000000.
    """
    # New trigger G000000 falls in S0039 window
    payload = dict(lvalert_content,
                   object={'graceid': 'G000011',
                           'gpstime': 1163905214.44,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3.02e-09,
                           'instruments': 'H1,L1',
                           'extra_attributes': {
                               'CoincInspiral': {
                                   'snr': 10.0}}},
                   alert_type='new',
                   uid='G000011')
    setattr(gracedb.client, 'event', SingleT0212TTPResponse)
    # addEventToSuperevent should be called
    # preferred event should be updated
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with(
            'S0039', preferred_event='G000011',
            t_0=None,
            t_end=pytest.approx(1163905239.44, abs=1e-3),
            t_start=pytest.approx(1163905213.44, abs=1e-3))


def test_single_ifo_4(mock_db):
    """Preferred event in superevent is a Multi-IFO Burst,
    new trigger is a CBC single. Preferred event is not updated
    """
    # New single IFO trigger G000013 falls in S0040 window
    payload = dict(lvalert_content,
                   object={'graceid': 'G000013',
                           'gpstime': 1078515565.0,
                           'group': 'CBC',
                           'pipeline': 'gstlal',
                           'far': 3.02e-31,
                           'instruments': 'H1',
                           'extra_attributes': {
                               'CoincInspiral': {
                                   'snr': 30.0}}},
                   alert_type='new',
                   uid='G000013')
    # addEventToSuperevent should be called
    # preferred event should not be updated
    with patch.object(gracedb.client, 'addEventToSuperevent') as p1, \
            patch.object(gracedb.client, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()
