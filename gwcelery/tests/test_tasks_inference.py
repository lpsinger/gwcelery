import configparser
import os
import subprocess

import pytest
from requests.exceptions import HTTPError
from unittest.mock import Mock

from .. import app
from ..tasks import condor
from ..tasks import inference


def mock_find_urls(available_frametypes):
    """Return mock gwdatafind.find_urls, which returns 'path_to_data' when
    input ifo and frametype are in available_frametypes.

    available_frametypes : dictionary
        Dictionary whose key is ifo and item is frametype
    """
    _available_frametypes = dict(
        (ifo[0], frametype) for ifo, frametype in available_frametypes.items())

    def _mock_find_url(ifo, frametype, start, end):
        data_exists = (ifo in _available_frametypes.keys() and
                       frametype == _available_frametypes[ifo])
        if data_exists:
            return ['path_to_data']
        else:
            return []

    return _mock_find_url


@pytest.mark.parametrize(
    'available_frametypes,answer',
    [[{}, None],
     [{'H1': app.conf['low_latency_frame_types']['H1']}, None],
     [app.conf['low_latency_frame_types'],
      app.conf['low_latency_frame_types']],
     [app.conf['high_latency_frame_types'],
      app.conf['high_latency_frame_types']]]
)
def test_query_data(monkeypatch, available_frametypes, answer):
    monkeypatch.setattr('gwcelery.tasks.inference.find_urls',
                        mock_find_urls(available_frametypes))
    if answer is None:
        with pytest.raises(inference.NotEnoughData):
            inference.query_data(1187008882)
    else:
        assert inference.query_data(1187008882) == answer


def test_upload_no_frametypes(monkeypatch):
    upload = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)
    inference.upload_no_frame_files(
        None, inference.NotEnoughData(), 'test', 'S1234')
    upload.assert_called_once()


def test_find_appropriate_cal_env(tmp_path):
    filepath = tmp_path / 'H_CalEnvs.txt'
    t1, cal1 = 1126259462, 'O1_calibration.txt'
    t2, cal2 = 1187008882, 'O2_calibration.txt'
    filepath.write_text('{t1} {cal1}\n{t2} {cal2}'.format(
            t1=t1, cal1=cal1, t2=t2, cal2=cal2))
    dir_name = str(tmp_path)
    trigtime_answer = [
        (t1 - 1, cal1), ((t1 + t2) / 2., cal1), (t2 + 1, cal2)]
    for trigtime, answer in trigtime_answer:
        assert os.path.basename(
            inference._find_appropriate_cal_env(trigtime, dir_name)) == answer


@pytest.mark.parametrize(
    'mc,q,sid,answers',
    [[1., 1., None,
      [('analysis', 'engine', 'lalinferencenest'),
       ('analysis', 'nparallel', '4'),
       ('analysis', 'roq', 'True'),
       ('paths', 'roq_b_matrix_directory',
        '/home/cbc/ROQ_data/IMRPhenomPv2/'),
       ('engine', 'approx', 'IMRPhenomPv2pseudoFourPN'),
       ('bayeswave', 'Nchain', '10'),
       ('bayeswave', 'Niter', '100000'),
       ('condor', 'bayeswave_request_memory', '16000'),
       ('condor', 'bayeswavepost_request_memory', '16000'),
       ('bayeswave', 'bw_srate', '4096')]],
     [10., 1., None,
      [('condor', 'bayeswave_request_memory', '1000'),
       ('condor', 'bayeswavepost_request_memory', '4000')]],
     [10., 1., 'S1234', []],
     [1., 1. / 10., None,
      [('analysis', 'engine', 'lalinferencenest'),
       ('analysis', 'nparallel', '4'),
       ('analysis', 'roq', 'True'),
       ('paths', 'roq_b_matrix_directory',
        '/home/cbc/ROQ_data/SEOBNRv4ROQ/'),
       ('engine', 'approx', 'SEOBNRv4_ROMpseudoFourPN')]],
     [1., 1. / 20., None,
      [('analysis', 'engine', 'lalinferencemcmc'),
       ('analysis', 'nparallel', '10'),
       ('analysis', 'roq', 'False'),
       ('engine', 'approx', 'SEOBNRv4_ROMpseudoFourPN'),
       ('engine', 'neff', '300')]]]
)
def test_prepare_ini(monkeypatch, mc, q, sid, answers):
    upload = Mock()

    def mock_calenv(trigtime, path):
        return 'path_to_calenv'

    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)
    monkeypatch.setattr(
        'gwcelery.tasks.inference._find_appropriate_cal_env',
        mock_calenv)
    monkeypatch.setitem(app.conf, 'gracedb_host', 'gracedb.ligo.org')

    m1 = mc * q**(-3. / 5.) * (1 + q)**(1. / 5.)
    m2 = q * m1
    event = {
        'gpstime': 1187008882,
        'graceid': 'G1234',
        'extra_attributes':
            {'SingleInspiral': [{'mass1': m1, 'mass2': m2, 'mchirp': mc}]}
    }
    config = configparser.ConfigParser()
    config.read_string(
        inference.prepare_ini(app.conf['low_latency_frame_types'], event, sid))
    for section, key, answer in answers:
        assert config[section][key] == answer

    if sid is not None:
        upload.assert_called_once()


def test_pre_pe_tasks(monkeypatch):
    event, sid = {'gpstime': 1187008882}, 'S1234'
    frametype_dict = app.conf['low_latency_frame_types']

    def mock_query_data(gpstime):
        return frametype_dict

    def mock_prepare_ini(f, e, s):
        assert f == frametype_dict
        assert e == event
        assert s == sid

    query_data = Mock(side_effect=mock_query_data)
    prepare_ini = Mock(side_effect=mock_prepare_ini)
    monkeypatch.setattr('gwcelery.tasks.inference.query_data.run', query_data)
    monkeypatch.setattr('gwcelery.tasks.inference.prepare_ini.run',
                        prepare_ini)

    inference.pre_pe_tasks(event, sid).delay()
    query_data.assert_called_once()
    prepare_ini.assert_called_once()


@pytest.mark.parametrize('psd', [b'psd', None])
def test_setup_dag_for_lalinference_(monkeypatch, tmp_path, psd):
    ini, coinc = 'ini', b'coinc'
    rundir = str(tmp_path)
    dag = 'lalinference dag'

    def _subprocess_run(cmd, **kwargs):
        assert cmd[0] == 'lalinference_pipe'
        del cmd[0]
        assert '--run-path' in cmd and '--coinc' in cmd
        idx = cmd.index('--run-path')
        assert cmd[idx + 1] == rundir
        del cmd[idx:idx + 2]
        idx = cmd.index('--coinc')
        path_to_coinc = cmd[idx + 1]
        with open(path_to_coinc, 'rb') as f:
            assert f.read() == coinc
        del cmd[idx:idx + 2]
        if psd is not None:
            assert '--psd' in cmd
            idx = cmd.index('--psd')
            path_to_psd = cmd[idx + 1]
            with open(path_to_psd, 'rb') as f:
                assert f.read() == psd
            del cmd[idx:idx + 2]
        path_to_ini, = cmd
        with open(os.path.join(rundir, 'multidag.dag'), 'w') as f:
            f.write(dag)

    monkeypatch.setattr('subprocess.run', _subprocess_run)
    path_to_dag = inference._setup_dag_for_lalinference(
        (coinc, psd), ini, rundir, 'S1234')
    with open(path_to_dag, 'r') as f:
        assert f.read() == dag


@pytest.mark.parametrize(
    'host', ['gracedb-playground.ligo.org', 'gracedb.ligo.org'])
def test_setup_dag_for_bilby(monkeypatch, tmp_path, host):
    event_coinc, rundir = ({}, b'coinc'), str(tmp_path)
    pid, sid = 'G1234', 'S1234'
    monkeypatch.setitem(app.conf, 'gracedb_host', host)
    dag = 'bilby dag'

    def _subprocess_run(cmd, **kwargs):
        is_quick_conf = 'o3replay' in cmd and 'FastTest' in cmd
        if host == 'gracedb.ligo.org':
            assert not is_quick_conf
        else:
            assert is_quick_conf
        with open(os.path.join(rundir, 'bilby_config.ini'), 'w') as f:
            f.write('bilby configuration ini file')
        dir = os.path.join(rundir, 'submit')
        os.mkdir(dir)
        with open(os.path.join(dir, 'dag_bilby.submit'), 'w') as f:
            f.write(dag)

    upload = Mock()
    monkeypatch.setattr('subprocess.run', _subprocess_run)
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)

    path_to_dag = inference._setup_dag_for_bilby(event_coinc, rundir, pid, sid)
    with open(path_to_dag, 'r') as f:
        assert f.read() == dag
    upload.assert_called_once()


@pytest.mark.parametrize('pipeline', ['lalinference', 'bilby'])
def test_setup_dag_for_failure(monkeypatch, tmp_path, pipeline):
    upload = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)
    monkeypatch.setattr('subprocess.run',
                        Mock(side_effect=subprocess.CalledProcessError(
                            1, ['cmd'], output=b'out', stderr=b'err')))

    rundir = str(tmp_path)

    with pytest.raises(subprocess.CalledProcessError):
        if pipeline == 'lalinference':
            inference._setup_dag_for_lalinference(
                (b'coinc', b'psd'), 'ini', rundir, 'S1234')
        elif pipeline == 'bilby':
            inference._setup_dag_for_bilby(
                ({}, b'coinc'), rundir, 'G1234', 'S1234')
    assert not os.path.exists(rundir)
    upload.assert_called_once()


@pytest.mark.parametrize('pipeline',
                         ['lalinference', 'bilby', 'my_awesome_pipeline'])
def test_dag_prepare_task(monkeypatch, pipeline):
    gid, sid = 'G1234', 'S1234'
    coinc, psd, ini, event = b'coinc', b'psd', 'ini', {'gpstime': 1187008882}
    rundir = 'rundir'
    path_to_dag = os.path.join(rundir, 'parameter_estimation.dag')

    def mock_download(filename, gid):
        if filename == 'coinc.xml':
            return coinc
        elif filename == 'psd.xml.gz':
            return psd

    def _setup_dag_for_lalinference(c_p, i, r, s):
        c, p = c_p
        assert (c == coinc and p == psd and i == ini
                and r == rundir and s == sid)
        return path_to_dag

    def _setup_dag_for_bilby(e_c, r, p, s):
        e, c = e_c
        assert (e == event and c == coinc and r == rundir
                and p == gid and s == sid)
        return path_to_dag

    def _subprocess_run(cmd, **kwargs):
        assert cmd == ['condor_submit_dag', '-no_submit', path_to_dag]

    mock_setup_dag_for_lalinference = \
        Mock(side_effect=_setup_dag_for_lalinference)
    mock_setup_dag_for_bilby = Mock(side_effect=_setup_dag_for_bilby)
    monkeypatch.setattr('gwcelery.tasks.gracedb.download.run', mock_download)
    monkeypatch.setattr('gwcelery.tasks.gracedb.get_event.run',
                        Mock(return_value=event))
    monkeypatch.setattr(
        'gwcelery.tasks.inference._setup_dag_for_lalinference.run',
        mock_setup_dag_for_lalinference)
    monkeypatch.setattr('gwcelery.tasks.inference._setup_dag_for_bilby.run',
                        mock_setup_dag_for_bilby)
    monkeypatch.setattr('subprocess.run', _subprocess_run)
    if pipeline in ['lalinference', 'bilby']:
        inference.dag_prepare_task(rundir, sid, gid, pipeline, ini).delay()
        if pipeline == 'lalinference':
            mock_setup_dag_for_lalinference.assert_called_once()
        elif pipeline == 'bilby':
            mock_setup_dag_for_bilby.assert_called_once()
    else:
        with pytest.raises(NotImplementedError):
            inference.dag_prepare_task(rundir, sid, gid, pipeline, ini).delay()


@pytest.mark.parametrize('exc', [condor.JobAborted(1, 'test'),
                                 condor.JobFailed(1, 'test')])
def test_job_error_notification(monkeypatch, tmp_path, exc):
    filenames = ['pe.log', 'pe.err', 'pe.out']
    for filename in filenames:
        with open(str(tmp_path / filename), 'w') as f:
            f.write('test')
    upload = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)

    inference.job_error_notification(
        None, exc, 'test', 'S1234', str(tmp_path), 'lalinference')
    assert upload.call_count == len(filenames) + 1


@pytest.mark.parametrize('pipeline',
                         ['lalinference', 'bilby', 'my_awesome_pipeline'])
def test_upload_url(monkeypatch, tmp_path, pipeline):
    upload = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)
    if pipeline in ['lalinference', 'bilby']:
        if pipeline == 'lalinference':
            path = str(tmp_path / 'posplots.html')
        else:
            path = str(tmp_path / 'home.html')
        with open(path, 'w') as f:
            f.write('test')
        inference._upload_url(str(tmp_path), 'G1234', pipeline)
        upload.assert_called_once()
    else:
        with pytest.raises(NotImplementedError):
            inference._upload_url(str(tmp_path), 'G1234', pipeline)


@pytest.mark.parametrize('pipeline',
                         ['lalinference', 'bilby', 'my_awesome_pipeline'])
def test_dag_finished(monkeypatch, tmp_path, pipeline):
    gid = 'G1234'
    rundir = str(tmp_path / 'rundir')
    resultdir = str(tmp_path / 'rundir/result')
    sampledir = str(tmp_path / 'rundir/final_result')
    pe_results_path = str(tmp_path / 'public_html/online_pe')
    monkeypatch.setitem(app.conf, 'pe_results_path', pe_results_path)
    pe_results_path = os.path.join(pe_results_path, gid, pipeline)
    os.makedirs(rundir)
    os.makedirs(resultdir)
    os.makedirs(sampledir)
    os.makedirs(pe_results_path)

    upload = Mock()
    _upload_url = Mock()
    create_label = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', upload)
    monkeypatch.setattr('gwcelery.tasks.inference._upload_url.run',
                        _upload_url)
    monkeypatch.setattr('gwcelery.tasks.gracedb.create_label.run',
                        create_label)

    if pipeline in ['lalinference', 'bilby']:
        if pipeline == 'lalinference':
            paths = [os.path.join(rundir,
                                  'lalinference_1187008756-1187008882.dag'),
                     os.path.join(rundir, 'glitch_median_PSD_forLI_H1.dat'),
                     os.path.join(rundir, 'glitch_median_PSD_forLI_L1.dat'),
                     os.path.join(rundir, 'glitch_median_PSD_forLI_V1.dat'),
                     os.path.join(rundir, 'posterior_samples.hdf5'),
                     os.path.join(pe_results_path, 'extrinsic.png'),
                     os.path.join(pe_results_path, 'sourceFrame.png')]
        else:
            input_sample = os.path.join(sampledir, "test_result.hdf5")
            with open(input_sample, 'wb') as f:
                f.write(b'result')
            monkeypatch.setattr('subprocess.run', Mock())
            paths = [os.path.join(sampledir, 'Bilby.posterior_samples.hdf5'),
                     os.path.join(resultdir, 'bilby_extrinsic_corner.png'),
                     os.path.join(resultdir, 'bilby_intrinsic_corner.png')]
        for path in paths:
            with open(path, 'wb') as f:
                f.write(b'result')

        inference.dag_finished(rundir, gid, 'S1234', pipeline)
        assert upload.call_count == len(paths)
        if pipeline == 'lalinference':
            _upload_url.assert_called_once()
        else:
            _upload_url.assert_not_called()
        if pipeline == 'bilby':
            create_label.assert_called_once()
        else:
            create_label.assert_not_called()
        assert not os.path.exists(rundir)
    else:
        with pytest.raises(NotImplementedError):
            inference.dag_finished(rundir, gid, 'S1234', pipeline)


def test_download_psd_failure(monkeypatch):
    monkeypatch.setattr('gwcelery.tasks.gracedb.download',
                        Mock(side_effect=HTTPError))
    assert inference._download_psd('G1234') is None


def test_start_pe(monkeypatch, tmp_path):
    path_to_sub = 'pe.dag.condor.sub'

    @app.task
    def mock_task():
        return path_to_sub

    dag_prepare_task = Mock(return_value=mock_task.s())

    def mock_condor_submit(path):
        assert path == path_to_sub

    condor_submit = Mock(side_effect=mock_condor_submit)
    dag_finished = Mock()
    monkeypatch.setattr('gwcelery.tasks.gracedb.upload.run', Mock())
    monkeypatch.setattr('distutils.dir_util.mkpath',
                        Mock(return_value=str(tmp_path)))
    monkeypatch.setattr('gwcelery.tasks.inference.dag_prepare_task',
                        dag_prepare_task)
    monkeypatch.setattr('gwcelery.tasks.condor.submit.run', condor_submit)
    monkeypatch.setattr('gwcelery.tasks.inference.dag_finished.run',
                        dag_finished)

    inference.start_pe('ini', 'G1234', 'S1234', 'lalinference')
    dag_prepare_task.assert_called_once()
    condor_submit.assert_called_once()
    dag_finished.assert_called_once()
