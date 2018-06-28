import pytest
from unittest.mock import patch

from ..tasks import gracedb, superevents
from . import resource_json


def test_update_preferred_event(monkeypatch):
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class NewEventTTPResponse(object):
        def json(self):
            return dict(graceid="T1234",
                        instruments="I1,J1,K1,L1,M1",
                        group="CBC",
                        superevent="some_superevent",
                        far=1e-30)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def event(self, gid):
                return T0212TTPResponse()

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    # call update _update_superevent such that updateSuperevent is called
    with patch.object(g, 'updateSuperevent') as p:
        superevents._update_superevent('S0039',
                                       'T0212',
                                       NewEventTTPResponse().json(),
                                       None,
                                       None)
        p.assert_called_with('S0039', preferred_event='T1234',
                             t_start=None, t_end=None, t_0=None)


def test_get_superevents(monkeypatch):
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())

    gid_1 = 'T0212'  # present in fake superevent queue
    gid_2 = 'T0219'  # present but not preferred event
    gid_3 = 'T9999'  # absent in fake superevent queue
    superevent_id_1, preferred_flag_1, r_1 = gracedb.get_superevents(gid_1)
    superevent_id_2, preferred_flag_2, r_2 = gracedb.get_superevents(gid_2)
    superevent_id_3, preferred_flag_3, r_3 = gracedb.get_superevents(gid_3)

    assert superevent_id_1 == 'S0039' and preferred_flag_1
    assert superevent_id_2 == 'S0041' and not preferred_flag_2
    assert superevent_id_3 is None


def test_parse_trigger_raising():
    garbage_payload = dict(some_value=999, something_else=99)
    with pytest.raises(KeyError):
        superevents.handle(garbage_payload)


# FIXME lot of redundancy, implement setUp tearDown for below
def test_parse_trigger_cbc_1(monkeypatch):
    """New trigger G000000, less significant than already
    existing superevent. Superevent window much larger than event
    window of G000000"""
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

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
            else:
                raise ValueError("Called with incorrect preferred event")
    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000000_cbc.json')
    # New trigger G000000 time falls in S0039 window
    # addEventToSuperevent should be called
    # updateSuperevent should not be updated
    with patch.object(g, 'addEventToSuperevent') as p1, \
            patch.object(g, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_not_called()


def test_parse_trigger_cbc_2(monkeypatch):
    """New trigger G000003, more significant than already
    existing superevent. Superevent window is much larger that
    event window of G000000"""
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                raise ValueError("Called with incorrect preferred event")
    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    # New trigger G000000 falls in S0039 window
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000003_cbc.json')
    # addEventToSuperevent should be called
    # preferred event should be updated
    with patch.object(g, 'addEventToSuperevent') as p1, \
            patch.object(g, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', preferred_event='G000003',
                                   t_0=None, t_start=None, t_end=None)


def test_parse_trigger_cbc_3(monkeypatch):
    """New trigger G000001, not present among superevents
    New superevent created"""
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000001_cbc.json')
    # G000001 absent in any superevent window, new superevent created
    # createSuperevent should be called exactly once
    with patch.object(g, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once()


def test_parse_trigger_cbc_4(monkeypatch):
    """New trigger G000002, doesn't pass far threshold"""
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000002_cbc.json')
    superevents.handle(payload)
    # neither method is called due to low far
    with patch.object(g, 'addEventToSuperevent') as p1, \
            patch.object(g, 'createSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_not_called()
        p2.assert_not_called()


def test_parse_trigger_burst_1(monkeypatch):
    """New cwb trigger G000005 with gpstime lying partially in
    S0039 window, not more significant than existing preferred
    event, superevent window changed.
    """
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

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
            else:
                raise ValueError("Called with incorrect preferred event")
    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000005_burst.json')
    # preferred event should not be updated
    # superevent window should change
    with patch.object(g, 'addEventToSuperevent') as p1, \
            patch.object(g, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', preferred_event=None, t_0=None,
                                   t_end=pytest.approx(1163905239, abs=1),
                                   t_start=pytest.approx(1163905214, abs=1))


def test_parse_trigger_burst_2(monkeypatch):
    """New LIB trigger G000006 with gpstime lying partially in
    S0039 window, more significant than already existing preferred
    event. superevent window changed
    """
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

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
            else:
                raise ValueError("Called with incorrect preferred event")
    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000006_burst.json')
    # preferred event not be updated, in spite of lower far of new event
    # because existing preferred event is CBC
    with patch.object(g, 'addEventToSuperevent') as p1, \
            patch.object(g, 'updateSuperevent') as p2:
        superevents.handle(payload)
        p1.assert_called_once()
        p2.assert_called_once_with('S0039', t_0=None, preferred_event=None,
                                   t_end=pytest.approx(1163905239, abs=1),
                                   t_start=pytest.approx(1163905214, abs=1))


def test_parse_trigger_burst_3(monkeypatch):
    """New LIB trigger G000007, not present among superevents
    New superevent created.
    Q_mean = frequency_mean = 100., hence d_t_start = d_t_end = 1s
    """
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            pass

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000007_burst.json')
    # G000007 absent in any superevent window, new superevent created
    with patch.object(g, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once_with(pytest.approx(1163905248.5),
                                  pytest.approx(1163905249.5),
                                  pytest.approx(1163905250.5),
                                  preferred_event='G000007')


def test_parse_trigger_burst_4(monkeypatch):
    """New CWB trigger G000008, not present among superevents
    New superevent created.
    extra attribute duration = 0.02s
    """
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            self._create_superevent_called += 1
            # values are such that the d_start and d_t_end are 1s
            # assert t_end - t_start == 0.04
            assert args[2] - args[0] == pytest.approx(0.04)
            assert kwargs.get('preferred_event') == 'G000008'

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

    g = FakeDb()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', g)
    payload = \
        resource_json(__name__, 'data/mock_trigger_new_G000008_burst.json')
    # G000008 absent in any superevent window, new superevent created
    with patch.object(g, 'createSuperevent') as p:
        superevents.handle(payload)
        p.assert_called_once()
