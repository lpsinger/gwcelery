from collections import defaultdict
from importlib import resources
from unittest import mock

from ..tasks import gracedb
from . import data


class DictMock(mock.MagicMock):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._defaultdict = defaultdict(self.__class__)

    def __getitem__(self, key):  # noqa: D105
        return self._defaultdict[key]


def patch(*args, **kwargs):
    return mock.patch(*args, **kwargs, new_callable=DictMock)


@patch('gwcelery.tasks.gracedb.client')
def test_create_event(mock_gracedb):
    event = gracedb.create_event(
        'filecontents', 'search', 'pipeline', 'group')
    mock_gracedb.events.create.assert_called_once_with(
        filename='initial.data', filecontents='filecontents', search='search',
        pipeline='pipeline', group='group', labels=())
    assert event['graceid'] == \
        mock_gracedb.events.create.return_value['graceid']


@patch('gwcelery.tasks.gracedb.client')
def test_create_superevent(mock_gracedb):
    superevent_id = gracedb.create_superevent(
        'graceid', 't_0', 't_start', 't_end')
    mock_gracedb.superevents.create.assert_called_once_with(
        preferred_event='graceid', t_0='t_0', t_start='t_start', t_end='t_end')
    assert superevent_id == mock_gracedb.superevents.create.return_value[
        'superevent_id']


@patch('gwcelery.tasks.gracedb.client')
def test_create_label(mock_gracedb):
    gracedb.create_label('label', 'graceid')
    mock_gracedb.events['graceid'].labels.create.assert_called_once_with(
        'label')


@patch('gwcelery.tasks.gracedb.client')
def test_remove_label(mock_gracedb):
    gracedb.remove_label('label', 'graceid')
    mock_gracedb.events['graceid'].labels.delete.assert_called_once_with(
        'label')


@patch('gwcelery.tasks.gracedb.client')
def test_create_signoff(mock_gracedb):
    """Create a label in GraceDB."""
    gracedb.create_signoff('status', 'comment', 'signoff_type', 'graceid')
    mock_gracedb.superevents['graceid'].signoff.assert_called_once_with(
        'signoff_type', 'status', 'comment')


@patch('gwcelery.tasks.gracedb.client')
@patch('gwcelery.tasks.gracedb.get_log',
       return_value=[{'filename': filename, 'N': i} for i, filename in
                     enumerate(['foo', 'bat', 'bat', 'baz'])])
def test_create_tag(mock_get_log, mock_gracedb):
    gracedb.create_tag('bat', 'tag', 'graceid')
    mock_get_log.assert_called_once_with('graceid')
    mock_gracedb.events['graceid'].logs[
        2].tags.create.assert_called_once_with('tag')


@patch('gwcelery.tasks.gracedb.client')
def test_create_voevent(mock_gracedb):
    gracedb.create_voevent('graceid', 'voevent_type',
                           skymap_filename='skymap_filename',
                           skymap_type='skymap_type')
    mock_gracedb.events['graceid'].voevents.create.assert_called_once_with(
        voevent_type='voevent_type',
        skymap_filename='skymap_filename',
        skymap_type='skymap_type')


@patch('gwcelery.tasks.gracedb.client')
def test_download(mock_gracedb):
    gracedb.download('filename', 'graceid')
    mock_gracedb.events['graceid'].files['filename'].get.assert_called_once()


@patch('gwcelery.tasks.gracedb.client')
def test_expose(mock_gracedb):
    gracedb.expose('graceid')
    mock_gracedb.superevents['graceid'].expose.assert_called_once_with()


@patch('gwcelery.tasks.gracedb.client')
def test_get_log(mock_gracedb):
    ret = gracedb.get_log('graceid')
    mock_gracedb.events['graceid'].logs.get.assert_called_once_with()
    assert ret == mock_gracedb.events['graceid'].logs.get.return_value


@patch('gwcelery.tasks.gracedb.client')
def test_get_superevent(mock_gracedb):
    gracedb.get_superevent('graceid')
    mock_gracedb.superevents['graceid'].get.assert_called_once_with()


@patch('gwcelery.tasks.gracedb.client')
def test_get_superevents(mock_gracedb):
    gracedb.get_superevents('query')
    mock_gracedb.superevents.search.assert_called_once_with(query='query')


@patch('gwcelery.tasks.gracedb.client')
def test_upload(mock_gracedb):
    gracedb.upload('filecontents', 'filename', 'graceid', 'message', 'tags')
    mock_gracedb.events['graceid'].logs.create.assert_called_once_with(
        comment='message', filename='filename', filecontents='filecontents',
        tags='tags')


@patch('gwcelery.tasks.gracedb.client')
def test_get_event(mock_gracedb):
    gracedb.get_event('G123456')
    mock_gracedb.events['G123456'].get.assert_called_once_with()


@patch('gwcelery.tasks.gracedb.client')
def test_get_group(mock_gracedb):
    result = gracedb.get_group('G123456')
    mock_gracedb.events['G123456'].get.assert_called_once_with()
    assert result == mock_gracedb.events['G123456'].get.return_value['group']


@patch('gwcelery.tasks.gracedb.client')
def test_get_search(mock_gracedb):
    result = gracedb.get_search('G123456')
    mock_gracedb.events['G123456'].get.assert_called_once_with()
    assert result == mock_gracedb.events['G123456'].get.return_value['search']


@patch('gwcelery.tasks.gracedb.client')
def test_get_events(mock_gracedb):
    gracedb.get_events(query='Some query')
    mock_gracedb.events.search.assert_called_once_with(query='Some query')


@patch('gwcelery.tasks.gracedb.client')
def test_get_labels(mock_gracedb):
    gracedb.get_labels('S1234')
    mock_gracedb.events['S1234'].labels.get.assert_called_once()


@patch('gwcelery.tasks.gracedb.client')
def test_replace_event(mock_gracedb):
    text = resources.read_binary(data, 'fermi_grb_gcn.xml')
    gracedb.replace_event(graceid='G123456', payload=text)
    mock_gracedb.events.update.assert_called_once_with('G123456',
                                                       filecontents=text)
