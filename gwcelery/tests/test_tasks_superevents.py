import pytest

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
                        superevent="some_superevent",
                        far=1e-30)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self.__update_superevent_called = False

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return NewEventTTPResponse()

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self.__update_superevent_called
            # function should be called only once
            self.__update_superevent_called = True

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    superevents._update_preferred_event('S0039', 'T0212', 'T1234')


def test_get_superevent(monkeypatch):
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
    superevent_id_1, preferred_flag_1, r_1 = gracedb.get_superevent(gid_1)
    superevent_id_2, preferred_flag_2, r_2 = gracedb.get_superevent(gid_2)
    superevent_id_3, preferred_flag_3, r_3 = gracedb.get_superevent(gid_3)

    assert superevent_id_1 == 'S0039' and preferred_flag_1
    assert superevent_id_2 == 'S0041' and not preferred_flag_2
    assert superevent_id_3 is None


def test_parse_trigger_raising():
    garbage_payload = dict(some_value=999, something_else=99)
    with pytest.raises(KeyError):
        superevents.handle(garbage_payload)


# FIXME lot of redundancy, implement setUp tearDown for below
def test_parse_trigger_1(monkeypatch):
    """New trigger G000000, less significant than already
    existing superevent"""
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class NewEventTTPResponse(object):
        def json(self):
            # hardcoding values of the new trigger G000000
            return dict(graceid="G000000",
                        instruments="H1,L1",
                        superevent="S0039",
                        far=3.021362523404484e-09)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._addevent_called = False

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._addevent_called
            self._addevent_called = True

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return NewEventTTPResponse()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    payload = resource_json(__name__, 'data/mock_trigger_new_G000000.json')
    # New trigger G000000 time falls in S0039 window
    superevents.handle(payload)


def test_parse_trigger_2(monkeypatch):
    """New trigger G000000, more significant than already
    existing superevent"""
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class NewEventTTPResponse(object):
        def json(self):
            # hacking the far of G000000 to a very low value
            return dict(graceid="G000000",
                        instruments="H1,L1",
                        superevent="S0039",
                        far=3.021362523404484e-31)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._update_superevent_called = False
            self._addevent_called = False

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._addevent_called
            self._addevent_called = True

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._update_superevent_called
            # function should be called only once
            self._update_superevent_called = True

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return NewEventTTPResponse()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    # New trigger G000000 falls in S0039 window
    payload = resource_json(__name__, 'data/mock_trigger_new_G000000.json')
    superevents.handle(payload)


def test_parse_trigger_3(monkeypatch):
    """New trigger G000001, not present among superevents
    New superevent created"""
    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._create_superevent_called = False

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._create_superevent_called
            self._create_superevent_called = True

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    payload = resource_json(__name__, 'data/mock_trigger_new_G000001.json')
    # G000001 absent in any superevent window, new superevent created
    superevents.handle(payload)


def test_parse_trigger_4(monkeypatch):
    """Restart scenario - G000001 not present, update alert
    received.
    Should give warning in captured log while running
    unittests"""
    class G000001TTPResponse(object):
        def json(self):
            # FIXME json packet currently has only necessary keys
            return dict(graceid="G000001",
                        instruments="H1,L1",
                        group="CBC",
                        pipeline="gstlal",
                        gpstime=1286741861.52678,
                        far=3.021362523404484e-31)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._create_superevent_called = False

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._create_superevent_called
            self._create_superevent_called = True

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def event(self, gid):
            return G000001TTPResponse()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    payload = resource_json(__name__, 'data/mock_trigger_update_G000001.json')
    # G000001 absent in any superevent window, update alert
    # triggers creation of a new superevent
    superevents.handle(payload)


def test_parse_trigger_5(monkeypatch):
    """Update alert comes in for already existing superevent T0211"""
    class T0212TTPResponse(object):
        def json(self):
            return resource_json(__name__, 'data/T0212_S0039_preferred.json')

    class T0211TTPResponse(object):
        def json(self):
            # The update will change the preferred event
            return dict(graceid="T0211",
                        instruments="H1,L1",
                        group="CBC",
                        pipeline="gstlal",
                        gpstime=1163905217.52678,
                        far=5.500858049414366e-20)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._update_superevent_called = False

        def superevents(self, **kwargs):
            response = resource_json(__name__, 'data/superevents.json')
            return (s for s in response['superevents'])

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return T0211TTPResponse()

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._update_superevent_called
            self._update_superevent_called = True

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    payload = resource_json(__name__, 'data/mock_trigger_update_T0211.json')
    superevents.handle(payload)
