from unittest.mock import patch

from ..tasks import gracedb


def test_create_event(monkeypatch):

    class MockResponse(object):

        def json(self):
            return {'graceid': 'T12345'}

    class MockGraceDb(object):

        def __init__(self, service):
            assert service == 'service'

        def createEvent(self, group, pipeline, filename, search=None,
                        labels=None, offline=False, filecontents=None,
                        **kwargs):
            assert group == 'group'
            assert pipeline == 'pipeline'
            assert filename == 'initial.data'
            assert search == 'search'
            assert filecontents == 'filecontents'
            return MockResponse()

    monkeypatch.setattr('ligo.gracedb.rest.GraceDb', MockGraceDb)

    graceid = gracedb.create_event('filecontents', 'search', 'pipeline',
                                   'group', 'service')
    assert graceid == 'T12345'


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_create_tag(mock_gracedb):
    # Run function under test.
    gracedb.create_tag('tag', 'n', 'graceid', 'service')

    # Check that GraceDb was instantiated once.
    mock_gracedb.assert_called_once_with('service')

    # Check that one file was downloaded.
    mock_gracedb.return_value.createTag.assert_called_once_with(
        'graceid', 'n', 'tag')


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_download(mock_gracedb):
    # Run function under test.
    gracedb.download('filename', 'graceid', 'service')

    # Check that GraceDb was instantiated once.
    mock_gracedb.assert_called_once_with('service')

    # Check that one file was downloaded.
    mock_gracedb.return_value.files.assert_called_once_with(
        'graceid', 'filename', raw=True)


def test_get_log(monkeypatch):

    class logs(object):

        def json(self):
            return {'log': 'stuff'}

    class MockGraceDb(object):

        def __init__(self, service):
            assert service == 'service'

        def logs(self, graceid):
            assert graceid == 'graceid'
            return logs()

    monkeypatch.setattr('ligo.gracedb.rest.GraceDb', MockGraceDb)

    # Run function under test.
    ret = gracedb.get_log('graceid', 'service')

    assert ret == 'stuff'


@patch('ligo.gracedb.rest.GraceDb', autospec=True)
def test_upload(mock_gracedb):
    # Run function under test.
    gracedb.upload(
        'filecontents', 'filename', 'graceid', 'service', 'message', 'tags')

    # Check that GraceDb was instantiated once.
    mock_gracedb.assert_called_once_with('service')

    # Check that one file was uploaded.
    mock_gracedb.return_value.writeLog.assert_called_once_with(
        'graceid', 'message', 'filename', 'filecontents', 'tags')
