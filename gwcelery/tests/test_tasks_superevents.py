import json

import pytest
import pkg_resources

from ..tasks import gracedb, superevent_manager


def test_set_preferred_event(monkeypatch):
    class T0212TTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/T0212_S0039_preferred.json') as f:
                return json.load(f)

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
    gracedb.set_preferred_event('S0039', 'T0212', 'T1234')


def test_get_superevent(monkeypatch):
    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'

        def get(self, url):
            return SuperEventsTTPResponse()

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
    garbage_text = json.dumps(garbage_payload)
    with pytest.raises(KeyError):
        superevent_manager.superevent_handler(garbage_text)


# FIXME lot of redundancy, implement setUp tearDown for below
def test_parse_trigger_1(monkeypatch):
    """New trigger G000000, less significant than already
    existing superevent"""
    class T0212TTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/T0212_S0039_preferred.json') as f:
                return json.load(f)

    class NewEventTTPResponse(object):
        def json(self):
            # hardcoding values of the new trigger G000000
            return dict(graceid="G000000",
                        instruments="H1,L1",
                        superevent="S0039",
                        far=3.021362523404484e-09)

    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._addevent_called = False

        def get(self, url):
            return SuperEventsTTPResponse()

        def addEventToSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._addevent_called
            self._addevent_called = True

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return NewEventTTPResponse()
    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    with pkg_resources.resource_stream(
            __name__, 'data/mock_trigger_new_G000000.json') as f:
        text = f.read()
    # New trigger G000000 time falls in S0039 window
    superevent_manager.superevent_handler(text)


def test_parse_trigger_2(monkeypatch):
    """New trigger G000000, more significant than already
    existing superevent"""
    class T0212TTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/T0212_S0039_preferred.json') as f:
                return json.load(f)

    class NewEventTTPResponse(object):
        def json(self):
            # hacking the far of G000000 to a very low value
            return dict(graceid="G000000",
                        instruments="H1,L1",
                        superevent="S0039",
                        far=3.021362523404484e-31)

    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._update_superevent_called = False
            self._addevent_called = False

        def get(self, url):
            return SuperEventsTTPResponse()

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
    with pkg_resources.resource_stream(
            __name__, 'data/mock_trigger_new_G000000.json') as f:
        text = f.read()
    superevent_manager.superevent_handler(text)


def test_parse_trigger_3(monkeypatch):
    """New trigger G000001, not present among superevents
    New superevent created"""
    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._create_superevent_called = False

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._create_superevent_called
            self._create_superevent_called = True

        def get(self, url):
            return SuperEventsTTPResponse()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    with pkg_resources.resource_stream(
            __name__, 'data/mock_trigger_new_G000001.json') as f:
        text = f.read()
    # G000001 absent in any superevent window, new superevent created
    superevent_manager.superevent_handler(text)


def test_parse_trigger_4(monkeypatch):
    """Restart scenario - G000001 not present, update alert
    received.
    Should give warning in captured log while running
    unittests"""
    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class G000001TTPResponse(object):
        def json(self):
            # FIXME json packet currently has only necessary keys
            return dict(graceid="G000001",
                        instruments="H1,L1",
                        gpstime=1286741861.52678,
                        far=3.021362523404484e-31)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._create_superevent_called = False

        def createSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._create_superevent_called
            self._create_superevent_called = True

        def get(self, url):
            return SuperEventsTTPResponse()

        def event(self, gid):
            return G000001TTPResponse()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    with pkg_resources.resource_stream(
            __name__, 'data/mock_trigger_update_G000001.json') as f:
        text = f.read()
    # G000001 absent in any superevent window, update alert
    # triggers creation of a new superevent
    superevent_manager.superevent_handler(text)


def test_parse_trigger_5(monkeypatch):
    """Update alert comes in for already existing superevent T0211"""
    class SuperEventsTTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/superevents.json') as f:
                return json.load(f)

    class T0212TTPResponse(object):
        def json(self):
            with pkg_resources.resource_stream(
                    __name__, 'data/T0212_S0039_preferred.json') as f:
                return json.load(f)

    class T0211TTPResponse(object):
        def json(self):
            # The update will change the preferred event
            return dict(graceid="T0211",
                        instruments="H1,L1",
                        gpstime=1163905217.52678,
                        far=5.500858049414366e-20)

    class FakeDb(object):
        def __init__(self):
            self.service_url = 'service_url'
            self._update_superevent_called = False

        def get(self, url):
            return SuperEventsTTPResponse()

        def event(self, gid):
            if gid == "T0212":
                return T0212TTPResponse()
            else:
                return T0211TTPResponse()

        def updateSuperevent(self, *args, **kwargs):    # noqa: N802
            assert not self._update_superevent_called
            self._update_superevent_called = True

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', FakeDb())
    with pkg_resources.resource_stream(
            __name__, 'data/mock_trigger_update_T0211.json') as f:
        text = f.read()
    superevent_manager.superevent_handler(text)
