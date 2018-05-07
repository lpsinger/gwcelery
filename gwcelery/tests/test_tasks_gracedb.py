from unittest.mock import patch

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
def test_create_tag(mock_gracedb):
    # Run function under test.
    gracedb.create_tag('tag', 'n', 'graceid')

    # Check that one file was downloaded.
    mock_gracedb.createTag.assert_called_once_with('graceid', 'n', 'tag')


@patch('gwcelery.tasks.gracedb.client', autospec=rest.GraceDb)
def test_download(mock_gracedb):
    # Run function under test.
    gracedb.download('filename', 'graceid')

    # Check that one file was downloaded.
    mock_gracedb.files.assert_called_once_with('graceid', 'filename', raw=True)


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
