from ..tasks import gracedb
from . import *


@patch('gwcelery.tasks.gracedb.GraceDb', autospec=True)
def test_download(mock_gracedb):
    # Run function under test.
    gracedb.download('filename', 'graceid', 'service')

    # Check that GraceDb was instantiated once.
    mock_gracedb.assert_called_once_with('service')

    # Check that one file was downloaded.
    mock_gracedb.return_value.files.assert_called_once_with(
        'graceid', 'filename', raw=True)


@patch('gwcelery.tasks.gracedb.GraceDb', autospec=True)
def test_upload(mock_gracedb):
    # Run function under test.
    gracedb.upload(
        'filecontents', 'filename', 'graceid', 'service', 'message', 'tags')

    # Check that GraceDb was instantiated once.
    mock_gracedb.assert_called_once_with('service')

    # Check that one file was uploaded.
    mock_gracedb.return_value.writeLog.assert_called_once_with(
        'graceid', 'message', 'filename', 'filecontents', 'tags')
