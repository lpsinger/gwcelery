"""Source Parameter Estimation with LALInference and Bilby."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import itertools
import json
import os
import shutil
import subprocess
import tempfile
import urllib

from celery import group
from gwdatafind import find_urls
import numpy as np
from requests.exceptions import HTTPError

from .. import app
from ..jinja import env
from . import condor
from . import gracedb


ini_name = 'online_lalinference_pe.ini'

executables = {'datafind': 'gw_data_find',
               'mergeNSscript': 'lalinference_nest2pos',
               'mergeMCMCscript': 'cbcBayesMCMC2pos',
               'combinePTMCMCh5script': 'cbcBayesCombinePTMCMCh5s',
               'resultspage': 'cbcBayesPostProc',
               'segfind': 'ligolw_segment_query',
               'ligolw_print': 'ligolw_print',
               'coherencetest': 'lalinference_coherence_test',
               'lalinferencenest': 'lalinference_nest',
               'lalinferencemcmc': 'lalinference_mcmc',
               'lalinferencebambi': 'lalinference_bambi',
               'lalinferencedatadump': 'lalinference_datadump',
               'ligo-skymap-from-samples': 'true',
               'ligo-skymap-plot': 'true',
               'processareas': 'process_areas',
               'computeroqweights': 'lalinference_compute_roq_weights',
               'mpiwrapper': 'lalinference_mpi_wrapper',
               'gracedb': 'gracedb',
               'ppanalysis': 'cbcBayesPPAnalysis',
               'pos_to_sim_inspiral': 'cbcBayesPosToSimInspiral',
               'bayeswave': 'BayesWave',
               'bayeswavepost': 'BayesWavePost'}


def _data_exists(end, frametype_dict):
    """Check whether data at end time can be found with gwdatafind and return
    true it it is found.
    """
    return min(
        len(
            find_urls(ifo[0], frametype_dict[ifo], end, end + 1)
        ) for ifo in frametype_dict.keys()
    ) > 0


class NotEnoughData(Exception):
    """Raised if found data is not enough due to the latency of data
    transfer
    """


@app.task(bind=True, autoretry_for=(NotEnoughData, ), default_retry_delay=1,
          max_retries=86400, retry_backoff=True, shared=False)
def query_data(self, trigtime):
    """Continues to query data until it is found with gwdatafind and return
    frametypes for the data. If data is not found in 86400 seconds = 1 day,
    raise NotEnoughData.
    """
    end = trigtime + 2
    if _data_exists(end, app.conf['low_latency_frame_types']):
        return app.conf['low_latency_frame_types']
    elif _data_exists(end, app.conf['high_latency_frame_types']):
        return app.conf['high_latency_frame_types']
    else:
        raise NotEnoughData


@app.task(ignore_result=True, shared=False)
def upload_no_frame_files(request, exc, traceback, superevent_id):
    """Upload notification when no frame files are found.

    Parameters
    ----------
    request : Context (placeholder)
        Task request variables
    exc : Exception
        Exception rased by condor.submit
    traceback : str (placeholder)
        Traceback message from a task
    superevent_id : str
        The GraceDB ID of a target superevent

    """
    if isinstance(exc, NotEnoughData):
        gracedb.upload.delay(
            filecontents=None, filename=None,
            graceid=superevent_id,
            message='Frame files have not been found.',
            tags='pe'
        )


def _find_appropriate_cal_env(trigtime, dir_name):
    """Return the path to the calibration uncertainties estimated at the time
    before and closest to the trigger time. If there are no calibration
    uncertainties estimated before the trigger time, return the oldest one. The
    gpstimes at which the calibration uncertainties were estimated and the
    names of the files containing the uncertaintes are saved in
    [HLV]_CalEnvs.txt.

    Parameters
    ----------
    trigtime : float
        The trigger time of a target event
    dir_name : str
        The path to the directory where files containing calibration
        uncertainties exist

    Return
    ------
    path : str
        The path to the calibration uncertainties appropriate for a target
        event

    """
    filename, = glob.glob(os.path.join(dir_name, '[HLV]_CalEnvs.txt'))
    calibration_index = np.atleast_1d(
        np.recfromtxt(filename, names=['gpstime', 'filename'])
    )
    gpstimes = calibration_index['gpstime']
    candidate_gpstimes = gpstimes < trigtime
    if np.any(candidate_gpstimes):
        idx = np.argmax(gpstimes * candidate_gpstimes)
        appropriate_cal = calibration_index['filename'][idx]
    else:
        appropriate_cal = calibration_index['filename'][np.argmin(gpstimes)]
    return os.path.join(dir_name, appropriate_cal.decode('utf-8'))


@app.task(shared=False)
def prepare_ini(frametype_dict, event, superevent_id=None):
    """Determine an appropriate PE settings for the target event and return ini
    file content for LALInference pipeline
    """
    # Get template of .ini file
    ini_template = env.get_template('online_pe.jinja2')

    # fill out the ini template and return the resultant content
    singleinspiraltable = event['extra_attributes']['SingleInspiral']
    trigtime = event['gpstime']
    ini_settings = {
        'gracedb_host': app.conf['gracedb_host'],
        'types': frametype_dict,
        'channels': app.conf['strain_channel_names'],
        'state_vector_channels': app.conf['state_vector_channel_names'],
        'webdir': os.path.join(
            app.conf['pe_results_path'], event['graceid'], 'lalinference'
        ),
        'paths': [{'name': name, 'path': find_executable(executable)}
                  for name, executable in executables.items()],
        'h1_calibration': _find_appropriate_cal_env(
            trigtime,
            '/home/cbc/pe/O3/calibrationenvelopes/LIGO_Hanford'
        ),
        'l1_calibration': _find_appropriate_cal_env(
            trigtime,
            '/home/cbc/pe/O3/calibrationenvelopes/LIGO_Livingston'
        ),
        'v1_calibration': _find_appropriate_cal_env(
            trigtime,
            '/home/cbc/pe/O3/calibrationenvelopes/Virgo'
        ),
        'mc': min([sngl['mchirp'] for sngl in singleinspiraltable]),
        'q': min([sngl['mass2'] / sngl['mass1']
                  for sngl in singleinspiraltable]),
        'mpirun': find_executable('mpirun')
    }
    ini_rota = ini_template.render(ini_settings)
    ini_settings.update({'use_of_ini': 'online'})
    ini_online = ini_template.render(ini_settings)
    # upload LALInference ini file to GraceDB
    if superevent_id is not None:
        gracedb.upload.delay(
            ini_rota, filename=ini_name, graceid=superevent_id,
            message=('Automatically generated LALInference configuration file'
                     ' for this event.'),
            tags='pe')

    return ini_online


def pre_pe_tasks(event, superevent_id):
    """Return canvas of tasks executed before parameter estimation starts"""
    return query_data.s(event['gpstime']).on_error(
        upload_no_frame_files.s(superevent_id)
    ) | prepare_ini.s(event, superevent_id)


@app.task(shared=False)
def _setup_dag_for_lalinference(coinc_psd, ini_contents,
                                rundir, superevent_id):
    """Create DAG for a lalinference run and return the path to DAG.

    Parameters
    ----------
    coinc_psd : tuple of byte contents
        Tuple of the byte contents of ``coinc.xml`` and ``psd.xml.gz``
    ini_contents : str
        The content of online_lalinference_pe.ini
    rundir : str
        The path to a run directory where the DAG file exits
    superevent_id : str
        The GraceDB ID of a target superevent

    Returns
    -------
    path_to_dag : str
        The path to the .dag file

    """
    coinc_contents, psd_contents = coinc_psd

    # write down coinc.xml in the run directory
    path_to_coinc = os.path.join(rundir, 'coinc.xml')
    with open(path_to_coinc, 'wb') as f:
        f.write(coinc_contents)

    # write down psd.xml.gz
    if psd_contents is not None:
        path_to_psd = os.path.join(rundir, 'psd.xml.gz')
        with open(path_to_psd, 'wb') as f:
            f.write(psd_contents)
        psd_arg = ['--psd', path_to_psd]
    else:
        psd_arg = []

    # write down .ini file in the run directory.
    path_to_ini = os.path.join(rundir, ini_name)
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    try:
        subprocess.run(
            ['lalinference_pipe', '--run-path', rundir,
             '--coinc', path_to_coinc, path_to_ini] + psd_arg,
            capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        contents = b'args:\n' + json.dumps(e.args[1]).encode('utf-8') + \
                   b'\n\nstdout:\n' + e.stdout + b'\n\nstderr:\n' + e.stderr
        gracedb.upload.delay(
            filecontents=contents, filename='pe_dag.log',
            graceid=superevent_id,
            message='Failed to prepare DAG for lalinference', tags='pe'
        )
        shutil.rmtree(rundir)
        raise
    else:
        # Remove the ini file so that people do not accidentally use this ini
        # file and hence online-PE-only nodes.
        os.remove(path_to_ini)

    return os.path.join(rundir, 'multidag.dag')


@app.task(shared=False)
def _setup_dag_for_bilby(
    event_coinc, rundir, preferred_event_id, superevent_id
):
    """Create DAG for a bilby run and return the path to DAG.

    Parameters
    ----------
    event_coinc : tuple
        Tuple of the json contents retrieved from gracedb.get_event() and
        the byte contents of coinc.xml
    rundir : str
        The path to a run directory where the DAG file exits
    preferred_event_id : str
        The GraceDB ID of a target preferred event
    superevent_id : str
        The GraceDB ID of a target superevent

    Returns
    -------
    path_to_dag : str
        The path to the .dag file

    """
    event, coinc = event_coinc

    path_to_json = os.path.join(rundir, 'event.json')
    with open(path_to_json, 'w') as f:
        json.dump(event, f, indent=2)

    path_to_coinc = os.path.join(rundir, 'coinc.xml')
    with open(path_to_coinc, 'wb') as f:
        f.write(coinc)

    path_to_webdir = os.path.join(
        app.conf['pe_results_path'], preferred_event_id, 'bilby'
    )

    setup_arg = ['bilby_pipe_gracedb', '--webdir', path_to_webdir,
                 '--outdir', rundir, '--json', path_to_json,
                 '--psd-file', path_to_coinc, '--online-pe']

    if not app.conf['gracedb_host'] == 'gracedb.ligo.org':
        setup_arg += ['--channel-dict', 'o3replay',
                      '--sampler-kwargs', 'FastTest']
    try:
        subprocess.run(setup_arg, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        contents = b'args:\n' + json.dumps(e.args[1]).encode('utf-8') + \
                   b'\n\nstdout:\n' + e.stdout + b'\n\nstderr:\n' + e.stderr
        gracedb.upload.delay(
            filecontents=contents, filename='pe_dag.log',
            graceid=superevent_id,
            message='Failed to prepare DAG for bilby', tags='pe'
        )
        shutil.rmtree(rundir)
        raise
    else:
        # Uploads bilby ini file to GraceDB
        group(upload_results_tasks(
            rundir, 'bilby_config.ini', superevent_id,
            'Automatically generated Bilby configuration file',
            'pe', 'online_bilby_pe.ini')).delay()

    path_to_dag, = glob.glob(os.path.join(rundir, 'submit/dag*.submit'))
    return path_to_dag


@app.task(shared=False)
def _condor_no_submit(path_to_dag):
    """Run 'condor_submit_dag -no_submit' and return the path to .sub file."""
    subprocess.run(['condor_submit_dag', '-no_submit', path_to_dag],
                   capture_output=True, check=True)
    return '{}.condor.sub'.format(path_to_dag)


@app.task(shared=False)
def dag_prepare_task(rundir, superevent_id, preferred_event_id, pe_pipeline,
                     ini_contents=None):
    """Return a canvas of tasks to prepare DAG.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    superevent_id : str
        The GraceDB ID of a target superevent
    preferred_event_id : str
        The GraceDB ID of a target preferred event
    pe_pipeline : str
        The parameter estimation pipeline used
        Either 'lalinference' OR 'bilby'
    ini_contents : str
        The content of online_lalinference_pe.ini
        Required if pe_pipeline == 'lalinference'

    Returns
    -------
    canvas : canvas of tasks
        The canvas of tasks to prepare DAG

    """
    if pe_pipeline == 'lalinference':
        canvas = group(
            gracedb.download.si('coinc.xml', preferred_event_id),
            _download_psd.si(preferred_event_id)
        ) | _setup_dag_for_lalinference.s(ini_contents, rundir, superevent_id)
    elif pe_pipeline == 'bilby':
        canvas = group(
            gracedb.get_event.si(preferred_event_id),
            gracedb.download.si('coinc.xml', preferred_event_id)
        ) | _setup_dag_for_bilby.s(rundir, preferred_event_id, superevent_id)
    else:
        raise NotImplementedError(f'Unknown PE pipeline {pe_pipeline}.')
    canvas |= _condor_no_submit.s()
    return canvas


def _find_paths_from_name(directory, name):
    """Return the paths of files or directories with given name under the
    specfied directory

    Parameters
    ----------
    directory : string
        Name of directory under which the target file or directory is searched
        for.
    name : string
        Name of target files or directories

    Returns
    -------
    paths : generator
        Paths to the target files or directories

    """
    return glob.iglob(os.path.join(directory, '**', name), recursive=True)


@app.task(ignore_result=True, shared=False)
def job_error_notification(request, exc, traceback,
                           superevent_id, rundir, pe_pipeline):
    """Upload notification when condor.submit terminates unexpectedly.

    Parameters
    ----------
    request : Context (placeholder)
        Task request variables
    exc : Exception
        Exception rased by condor.submit
    traceback : str (placeholder)
        Traceback message from a task
    superevent_id : str
        The GraceDB ID of a target superevent
    rundir : str
        The run directory for PE
    pe_pipeline : str
        The parameter estimation pipeline used
        Either lalinference OR bilby

    """
    if isinstance(exc, condor.JobAborted):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id, tags='pe',
            message='The {} condor job was aborted.'.format(pe_pipeline)
        )
    elif isinstance(exc, condor.JobFailed):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id, tags='pe',
            message='The {} condor job failed.'.format(pe_pipeline)
        )
    # Get paths to .log files, .err files, .out files
    paths_to_log = _find_paths_from_name(rundir, '*.log')
    paths_to_err = _find_paths_from_name(rundir, '*.err')
    paths_to_out = _find_paths_from_name(rundir, '*.out')
    # Upload .log and .err files
    for path in itertools.chain(paths_to_log, paths_to_err, paths_to_out):
        with open(path, 'rb') as f:
            contents = f.read()
        if contents:
            # put .log suffix in log file names so that users can directly
            # read the contents instead of downloading them when they click
            # file names
            gracedb.upload.delay(
                filecontents=contents,
                filename=os.path.basename(path) + '.log',
                graceid=superevent_id,
                message='A log file for {} condor job.'.format(pe_pipeline),
                tags='pe'
            )


@app.task(ignore_result=True, shared=False)
def _upload_url(pe_results_path, graceid, pe_pipeline):
    """Upload url of a page containing all of the plots."""
    if pe_pipeline == 'lalinference':
        path_to_posplots, = _find_paths_from_name(
            pe_results_path, 'posplots.html'
        )
    elif pe_pipeline == 'bilby':
        path_to_posplots, = _find_paths_from_name(
            pe_results_path, 'home.html'
        )
    else:
        raise NotImplementedError(f'Unknown PE pipeline {pe_pipeline}.')

    baseurl = urllib.parse.urljoin(
                  app.conf['pe_results_url'],
                  os.path.relpath(
                      path_to_posplots,
                      app.conf['pe_results_path']
                  )
              )
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=graceid,
        message=('Online {} parameter estimation finished.'
                 '<a href={}>results</a>').format(pe_pipeline, baseurl),
        tags='pe'
    )


def upload_results_tasks(pe_results_path, filename, graceid, message, tag,
                         uploaded_filename=None):
    """Return tasks to get the contents of PE result files and upload them to
    GraceDB.

    Parameters
    ----------
    pe_results_path : string
        Directory under which the target file located.
    filename : string
        Name of the target file
    graceid : string
        GraceDB ID
    message : string
        Message uploaded to GraceDB
    tag : str
        Name of tag to add the GraceDB log
    uploaded_filename : str
        Name of the uploaded file. If not supplied, it is the same as the
        original file name.

    Returns
    -------
    tasks : list of celery tasks

    """
    tasks = []
    for path in _find_paths_from_name(pe_results_path, filename):
        if uploaded_filename is None:
            _uploaded_filename = os.path.basename(path)
        else:
            _uploaded_filename = uploaded_filename
        with open(path, 'rb') as f:
            tasks.append(gracedb.upload.si(f.read(), _uploaded_filename,
                                           graceid, message, tag))
    return tasks


@app.task(ignore_result=True, shared=False)
def clean_up(rundir):
    """Clean up a run directory.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits

    """
    shutil.rmtree(rundir)


@app.task(ignore_result=True, shared=False)
def dag_finished(rundir, preferred_event_id, superevent_id, pe_pipeline):
    """Upload PE results and clean up run directory

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    preferred_event_id : str
        The GraceDB ID of a target preferred event
    superevent_id : str
        The GraceDB ID of a target superevent
    pe_pipeline : str
        The parameter estimation pipeline used
        Either lalinference OR bilby

    Returns
    -------
    tasks : canvas
        The work-flow for uploading PE results

    """
    pe_results_path = os.path.join(
        app.conf['pe_results_path'], preferred_event_id, pe_pipeline
    )

    if pe_pipeline == 'lalinference':
        uploads = [
            (rundir, 'glitch_median_PSD_forLI_*.dat',
             'Bayeswave PSD used for LALInference PE', None),
            (rundir, 'lalinference*.dag', 'LALInference DAG', None),
            (rundir, 'posterior*.hdf5',
             'LALInference posterior samples',
             'LALInference.posterior_samples.hdf5'),
            (pe_results_path, 'extrinsic.png',
             'LALInference corner plot for extrinsic parameters',
             'LALInference.extrinsic.png'),
            (pe_results_path, 'sourceFrame.png',
             'LALInference corner plot for source frame parameters',
             'LALInference.intrinsic.png')
        ]
    elif pe_pipeline == 'bilby':
        resultdir = os.path.join(rundir, 'result')
        sampledir = os.path.join(rundir, 'final_result')
        sample_filename = 'Bilby.posterior_samples.hdf5'
        input_sample, = glob.glob(os.path.join(sampledir, '*result.hdf5'))
        subprocess.run(
            ['bilby_pipe_to_ligo_skymap_samples', input_sample,
             '--out', os.path.join(sampledir, sample_filename)])
        uploads = [
            (sampledir, sample_filename,
             'Bilby posterior samples',
             sample_filename),
            (resultdir, '*_extrinsic_corner.png',
             'Bilby corner plot for extrinsic parameters',
             'Bilby.extrinsic.png'),
            (resultdir, '*_intrinsic_corner.png',
             'Bilby corner plot for intrinsic parameters',
             'Bilby.intrinsic.png')
        ]
    else:
        raise NotImplementedError(f'Unknown PE pipeline {pe_pipeline}.')

    upload_tasks = []
    for dir, name1, comment, name2 in uploads:
        upload_tasks += upload_results_tasks(
            dir, name1, superevent_id, comment, 'pe', name2)

    chain = group(upload_tasks) | clean_up.si(rundir)
    if pe_pipeline == 'lalinference':
        chain = \
            _upload_url.si(pe_results_path, superevent_id, pe_pipeline) | chain
    chain.delay()

    if pe_pipeline == 'bilby':
        gracedb.create_label.delay('PE_READY', superevent_id)


@gracedb.task(shared=False)
def _download_psd(gid):
    """Download ``psd.xml.gz`` and return its content. If that file does not
    exist, return None.
    """
    try:
        return gracedb.download("psd.xml.gz", gid)
    except HTTPError:
        return None


@app.task(ignore_result=True, shared=False)
def start_pe(ini_contents, preferred_event_id, superevent_id, pe_pipeline):
    """Run Parameter Estimation on a given event.

    Parameters
    ----------
    ini_contents : str
        The content of online_lalinference_pe.ini
    preferred_event_id : str
        The GraceDB ID of a target preferred event
    superevent_id : str
        The GraceDB ID of a target superevent
    pe_pipeline : str
        The parameter estimation pipeline used
        lalinference OR bilby

    """
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=superevent_id,
        message=('Starting {} online parameter estimation '
                 'for {}').format(pe_pipeline, preferred_event_id),
        tags='pe'
    )

    # make a run directory
    pipeline_dir = os.path.expanduser('~/.cache/{}'.format(pe_pipeline))
    mkpath(pipeline_dir)
    rundir = tempfile.mkdtemp(
        dir=pipeline_dir, prefix='{}_'.format(superevent_id)
    )

    # give permissions to read the files under the run directory so that PE
    # ROTA people can check the status of parameter estimation.
    os.chmod(rundir, 0o755)

    canvas = (
        dag_prepare_task(
            rundir, superevent_id, preferred_event_id,
            pe_pipeline, ini_contents
        )
        |
        condor.submit.s().on_error(
            job_error_notification.s(superevent_id, rundir, pe_pipeline)
        )
        |
        dag_finished.si(
            rundir, preferred_event_id, superevent_id, pe_pipeline
        )
    )
    canvas.delay()
