from unittest.mock import patch
from pkg_resources import resource_string

from ligo.gracedb import rest

from ..tasks import gracedb


def test_create_event(monkeypatch):

    class MockResponse(object):

        def json(self):
            return {'graceid': 'T12345'}

    class MockGraceDb(object):

        def createEvent(self, group, pipeline, filename,  # noqa: N802
                        search=None, labels=None, offline=False,
                        filecontents=None, **kwargs):
            assert group == 'group'
            assert pipeline == 'pipeline'
            assert filename == 'initial.data'
            assert search == 'search'
            assert filecontents == 'filecontents'
            return MockResponse()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', MockGraceDb())

    graceid = gracedb.create_event('filecontents', 'search', 'pipeline',
                                   'group')
    assert graceid == 'T12345'


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_create_label(mock_gracedb):
    # Run function under test.
    gracedb.create_label('label', 'graceid')

    # Check that one file was downloaded.
    mock_gracedb.writeLabel.assert_called_once_with('graceid', 'label')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_remove_label(mock_gracedb):
    # Run function under test.
    gracedb.remove_label('label', 'graceid')

    # Check that one file was downloaded.
    mock_gracedb.removeLabel.assert_called_once_with('graceid', 'label')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_create_signoff(mock_gracedb):
    """Create a label in GraceDB."""
    gracedb.create_signoff('status', 'comment', 'signoff_type', 'graceid')
    mock_gracedb.create_signoff.assert_called_once_with(
        'graceid', 'signoff_type', 'status', 'comment')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'filename': filename, 'N': i} for i, filename in
                     enumerate(['foo', 'bar', 'bat', 'baz'])])
def test_create_tag(mock_get_log, mock_gracedb):
    gracedb.create_tag('bat', 'tag', 'graceid')
    mock_get_log.assert_called_once_with('graceid')
    mock_gracedb.addTag.assert_called_once_with('graceid', 2, 'tag')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_create_voevent(mock_gracedb):
    # Run function under test.
    gracedb.create_voevent('graceid', 'voevent_type',
                           skymap_filename='skymap_filename',
                           skymap_type='skymap_type')

    # Check that one file was downloaded.
    mock_gracedb.createVOEvent.assert_called_once_with(
        'graceid', 'voevent_type',
        skymap_filename='skymap_filename',
        skymap_type='skymap_type')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_download(mock_gracedb):
    # Run function under test.
    gracedb.download('filename', 'graceid')

    # Check that one file was downloaded.
    mock_gracedb.files.assert_called_once_with('graceid', 'filename', raw=True)


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_expose(mock_gracedb):
    gracedb.expose('graceid')
    mock_gracedb.modify_permissions.assert_called_once_with(
        'graceid', 'expose')


def test_get_log(monkeypatch):

    class logs(object):  # noqa: N801

        def json(self):
            return {'log': 'stuff'}

    class MockGraceDb(object):

        def logs(self, graceid):
            assert graceid == 'graceid'
            return logs()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', MockGraceDb())

    # Run function under test.
    ret = gracedb.get_log('graceid')

    assert ret == 'stuff'


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_get_superevent(mock_gracedb):
    # Run function under test.
    gracedb.get_superevent('graceid')

    # Check that one file was downloaded.
    mock_gracedb.superevent.assert_called_once_with('graceid')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_get_superevents(mock_gracedb):
    gracedb.get_superevents('query')
    mock_gracedb.superevents.assert_called_once_with('query', orderby='t_0')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_upload(mock_gracedb):
    # Run function under test.
    gracedb.upload('filecontents', 'filename', 'graceid', 'message', 'tags')

    # Check that one file was uploaded.
    mock_gracedb.writeLog.assert_called_once_with(
        'graceid', 'message', 'filename', 'filecontents', 'tags')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_get_event(mock_gracedb):
    gracedb.get_event('G123456')
    mock_gracedb.event.assert_called_once_with('G123456')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_get_events(mock_gracedb):
    gracedb.get_events(query='Some query', orderby=None,
                       count=None, columns=None)
    mock_gracedb.events.assert_called_once_with(query='Some query',
                                                orderby=None, count=None,
                                                columns=None)


def test_get_labels(monkeypatch):

    class MockResponse(object):

        def json(self):
            return {'labels': [{'name': 'LABEL1'}, {'name': 'LABEL2'}]}

    class MockGraceDb(object):

        def labels(self, graceid):
            assert graceid == 'S1234'
            return MockResponse()

    monkeypatch.setattr('gwcelery.tasks.gracedb.client', MockGraceDb())
    labels = gracedb.get_labels('S1234')
    assert labels == {'LABEL1', 'LABEL2'}


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_replace_event(mock_gracedb):
    text = resource_string(__name__, 'data/fermi_grb_gcn.xml')
    gracedb.replace_event(graceid='G123456', payload=text)
    mock_gracedb.replaceEvent.assert_called_once_with(graceid='G123456',
                                                      filename='initial.data',
                                                      filecontents=text)
