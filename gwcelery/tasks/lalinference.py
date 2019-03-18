"""Source Parameter Estimation with LALInference."""
from distutils.spawn import find_executable
from distutils.dir_util import mkpath
import glob
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
import urllib

from celery import group
from glue.lal import Cache
from gwdatafind import find_urls
from gwpy.timeseries import StateVector
import lal
import lalsimulation

from .. import app
from ..jinja import env
from . import condor
from . import gracedb
from . import skymaps


ini_name = 'online_pe.ini'

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
               'ligo-skymap-from-samples': 'ligo-skymap-from-samples',
               'ligo-skymap-plot': 'ligo-skymap-plot',
               'processareas': 'process_areas',
               'computeroqweights': 'lalinference_compute_roq_weights',
               'mpiwrapper': 'lalinference_mpi_wrapper',
               'gracedb': 'gracedb',
               'ppanalysis': 'cbcBayesPPAnalysis',
               'pos_to_sim_inspiral': 'cbcBayesPosToSimInspiral'}

flow = 20.0

# number of samples between end time of the data used for psd estimation and
# start time of data for PE
padding = 16

# default number of realizations used for PSD estimation
default_num_of_realizations = 32


def _ifos(event):
    """Return ifos"""
    return event['extra_attributes']['CoincInspiral']['ifos'].split(',')


def _chirplen(singleinspiral):
    """Return chirplen"""
    return lalsimulation.SimInspiralChirpTimeBound(
               flow,
               singleinspiral['mass1'] * lal.MSUN_SI,
               singleinspiral['mass2'] * lal.MSUN_SI,
               0.0, 0.0
           )


def _round_up_to_power_of_two(x):
    """Return smallest power of two exceeding x"""
    return 2**math.ceil(math.log(x, 2))


def _seglen(singleinspiraltable):
    """Return seglen"""
    return max([_round_up_to_power_of_two(max(4.0, _chirplen(sngl) + 2.0))
                for sngl in singleinspiraltable])


def _freq_dict(freq, ifos):
    """Return dictionary whose keys are ifos and items are frequencies"""
    return dict((ifo, freq) for ifo in ifos)


def _fstop(singleinspiral):
    """Return final frequency"""
    return lalsimulation.IMRPhenomDGetPeakFreq(
               singleinspiral['mass1'], singleinspiral['mass2'], 0.0, 0.0
           )


def _srate(singleinspiraltable):
    """Return srate we should use"""
    return _round_up_to_power_of_two(
               max([_fstop(sngl) for sngl in singleinspiraltable])
           ) * 2


def _data_exists(end, ifos, frametype_dict):
    """Check whether data at end time can be found with gwdatafind and return
    true it it is found.
    """
    return min(
        len(
            find_urls(ifo[0], frametype_dict[ifo], end, end + 1)
        ) for ifo in ifos
    ) > 0


class NotEnoughData(Exception):
    """Raised if found data is not enough due to the latency of data
    transfer
    """


@app.task(bind=True, autoretry_for=(NotEnoughData, ), default_retry_delay=1,
          max_retries=86400, retry_backoff=True, shared=False)
def query_data(self, trigtime, ifos):
    """Continues to query data until it is found with gwdatafind and return
    frametypes for the data. If data is not found in 86400 seconds = 1 day,
    raise NotEnoughData.
    """
    end = trigtime + 2
    if _data_exists(end, ifos, app.conf['low_latency_frame_types']):
        return app.conf['low_latency_frame_types']
    elif _data_exists(end, ifos, app.conf['high_latency_frame_types']):
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
        The GraceDb ID of a target superevent
    """
    if isinstance(exc, NotEnoughData):
        gracedb.upload.delay(
            filecontents=None, filename=None,
            graceid=superevent_id,
            message='Frame files have not been found.',
            tags='pe'
        )


def _upload_no_pe_ready_data(superevent_id):
    """Upload comments if data quality is not good enough for PE"""
    gracedb.upload.delay(
        filecontents=None, filename=None,
        graceid=superevent_id,
        message=('Data quality is not good enough. '
                 'Parameter Estimation will never start automatically.'),
        tags='pe'
    )


def _find_appropriate_psdstart_psdlength(
    trigtime, seglen, ifos, frametype_dict, superevent_id=None
):
    """Check data quality with statevector and decide psdstart and psdlength
    automatically. If enough data is not found, raise exception and report
    failure to GraceDB.

    Parameters
    ----------
    trigtime : float
        The trigger time
    seglen : int
        The length of data used for overlap calculation
    ifos : list of str
        eg. ['H1', 'L1', 'V1']
    frametype_dict : dictionary
        The dictionary relating ifos with frametypes
        eg. {'H1': 'H1_llhoft', 'L1': 'L1_llhoft', 'V1': 'V1_llhoft'}

    Returns
    -------
    psdstart : float
        The GSP start time of PSD estimation
    psdlength : int
        The length of data used for PSD estimation
    """
    ideal_start_time = \
        trigtime + 2 - seglen - padding - default_num_of_realizations * seglen
    ideal_end_time = trigtime + 2

    # check data quality and shorten data if it is not good enough for PE
    start_times, end_times = [], []
    for ifo in ifos:
        datacache = Cache.from_urls(
            find_urls(ifo[0], frametype_dict[ifo],
                      ideal_start_time, ideal_end_time)
        )
        flag = StateVector.read(
                   datacache, app.conf['state_vector_channel_names'][ifo],
                   start=ideal_start_time, end=ideal_end_time,
                   bits=["HOFT_OK", "OBSERVATION_INTENT", "OBSERVATION_READY"]
               ).to_dqflags()
        try:
            pe_segment = (flag['HOFT_OK'].active -
                          ~flag['OBSERVATION_INTENT'].active -
                          ~flag['OBSERVATION_READY'].active)[-1]
        except IndexError:
            if superevent_id is not None:
                _upload_no_pe_ready_data(superevent_id)
            raise
        start_times.append(pe_segment[0])
        end_times.append(pe_segment[1])
    start = max(start_times)
    end = min(end_times)

    # Make sure that we have at least one realization for PSD estimation. The
    # end time threshold is endtime - 1.0 because Virgo's statevector has
    # sampling rate of 1 Hz and resultant end time after statevector reading
    # can be input end time - 1.0 second
    if start <= trigtime + 2 - seglen - padding - seglen and end >= end - 1.0:  # noqa
        psdlength = math.floor(
            trigtime + 2 - seglen - padding - start
        ) // seglen * seglen
        return (trigtime + 2 - seglen - padding - psdlength, psdlength)
    else:
        if superevent_id is not None:
            _upload_no_pe_ready_data(superevent_id)
        raise


@app.task(shared=False)
def prepare_ini(frametype_dict, event, superevent_id=None):
    """Determine an appropriate PE settings for the target event and return ini
    file content
    """
    # Get template of .ini file
    ini_template = env.get_template('online_pe.jinja2')

    # Download event's info to determine PE settings
    singleinspiraltable = event['extra_attributes']['SingleInspiral']
    trigtime = event['gpstime']

    # fill out the ini template and return the resultant content
    ifos = _ifos(event)
    seglen = _seglen(singleinspiraltable)
    # FIXME: seglen here might not be actual seglen if ROQ is used
    psdstart, psdlength = \
        _find_appropriate_psdstart_psdlength(
            trigtime, seglen, ifos, frametype_dict, superevent_id
        )
    ini_settings = {
        'service_url': gracedb.client._service_url,
        'types': frametype_dict,
        'channels': app.conf['strain_channel_names'],
        'webdir': os.path.join(app.conf['pe_results_path'], event['graceid']),
        'paths': [{'name': name, 'path': find_executable(executable)}
                  for name, executable in executables.items()],
        'q': min([sngl['mass2'] / sngl['mass1']
                  for sngl in singleinspiraltable]),
        'ifos': ifos,
        'seglen': seglen,
        'flow': _freq_dict(flow, ifos),
        'srate': _srate(singleinspiraltable),
        'gps_start_time': psdstart - 1.0,  # to be smaller than psdstart
        'gps_end_time': trigtime + 3.0,  # to be larger than trigtime + 2.0
        'psd_start_time': psdstart,
        'psd_length': psdlength
    }
    return ini_template.render(ini_settings)


def pre_pe_tasks(event, superevent_id):
    """Return canvas of tasks executed before parameter estimation starts"""
    return query_data.s(event['gpstime'], _ifos(event)).on_error(
        upload_no_frame_files.s(superevent_id)
    ) | prepare_ini.s(event, superevent_id)


@app.task(shared=False)
def dag_prepare(rundir, ini_contents, preferred_event_id, superevent_id):
    """Create a Condor DAG to run LALInference on a given event.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    ini_contents : str
        The content of online_pe.ini
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent

    Returns
    -------
    submit_file : str
        The path to the .sub file
    """
    # write down .ini file in the run directory
    path_to_ini = rundir + '/' + ini_name
    with open(path_to_ini, 'w') as f:
        f.write(ini_contents)

    # run lalinference_pipe
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=superevent_id,
        message='starting LALInference online parameter estimation',
        tags='pe'
    )
    try:
        subprocess.run(['lalinference_pipe', '--run-path', rundir,
                        '--gid', preferred_event_id, path_to_ini],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True)
        subprocess.run(['condor_submit_dag', '-no_submit',
                        rundir + '/multidag.dag'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True)
    except subprocess.CalledProcessError as e:
        contents = b'args:\n' + json.dumps(e.args[1]).encode('utf-8') + \
                   b'\n\nstdout:\n' + e.stdout + b'\n\nstderr:\n' + e.stderr
        gracedb.upload.delay(
            filecontents=contents, filename='pe_dag.log',
            graceid=superevent_id,
            message='Failed to prepare DAG', tags='pe'
        )
        shutil.rmtree(rundir)
        raise

    return rundir + '/multidag.dag.condor.sub'


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
def job_error_notification(request, exc, traceback, superevent_id, rundir):
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
        The GraceDb ID of a target superevent
    rundir : str
        The run directory for PE
    """
    if isinstance(exc, condor.JobAborted):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job was aborted.', tags='pe'
        )
    elif isinstance(exc, condor.JobFailed):
        gracedb.upload.delay(
            filecontents=None, filename=None, graceid=superevent_id,
            message='Job failed.', tags='pe'
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
            gracedb.upload.delay(
                filecontents=contents, filename=os.path.basename(path),
                graceid=superevent_id,
                message='Here is a log file for PE.',
                tags='pe'
            )


@app.task(ignore_result=True, shared=False)
def _upload_url(pe_results_path, graceid):
    """Upload url of a page containing all of the plots."""
    path_to_posplots, = _find_paths_from_name(pe_results_path, 'posplots.html')
    baseurl = urllib.parse.urljoin(
                  app.conf['pe_results_url'],
                  os.path.relpath(
                      path_to_posplots,
                      app.conf['pe_results_path']
                  )
              )
    gracedb.upload.delay(
        filecontents=None, filename=None, graceid=graceid,
        message=('LALInference online parameter estimation finished.'
                 '<a href={}>results</a>').format(baseurl),
        tags='pe'
    )


@app.task(ignore_result=True, shared=False)
def _get_result_contents(pe_results_path, filename):
    """Return the contents of a PE results file by reading it from the local
    filesystem.
    """
    path, = _find_paths_from_name(pe_results_path, filename)
    with open(path, 'rb') as f:
        contents = f.read()
    return contents


def _upload_result(pe_results_path, filename, graceid, message, tag):
    """Return a canvas to get the contents of a PE result file and upload it to
    GraceDb.
    """
    return _get_result_contents.si(pe_results_path, filename) | \
        gracedb.upload.s(filename, graceid, message, tag)


def _upload_skymap(pe_results_path, graceid):
    return _get_result_contents.si(pe_results_path, 'LALInference.fits') | \
        group(
            skymaps.annotate_fits('LALInference.fits',
                                  graceid, ['pe', 'sky_loc']),
            gracedb.upload.s('LALInference.fits', graceid,
                             'LALInference FITS sky map', ['pe', 'sky_loc'])
        )


@app.task(ignore_result=True, shared=False)
def clean_up(rundir):
    """Clean up a run directory.

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    """
    shutil.rmtree(rundir)


def dag_finished(rundir, preferred_event_id, superevent_id):
    """Upload PE results and clean up run directory

    Parameters
    ----------
    rundir : str
        The path to a run directory where the DAG file exits
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent

    Returns
    -------
    tasks : canvas
        The work-flow for uploading PE results
    """
    # get path to pe results
    pe_results_path = \
        os.path.join(app.conf['pe_results_path'], preferred_event_id)

    # FIXME: _upload_url.si has to be out of group for gracedb.create_label.si
    # to run
    return \
        _upload_url.si(pe_results_path, superevent_id) | \
        group(
            _upload_skymap(pe_results_path, superevent_id),
            _upload_result(
                pe_results_path, 'extrinsic.png', superevent_id,
                'Corner plot for extrinsic parameters', 'pe'
            ),
            _upload_result(
                pe_results_path, 'intrinsic.png', superevent_id,
                'Corner plot for intrinsic parameters', 'pe'
            ),
            _upload_result(
                pe_results_path, 'sourceFrame.png', superevent_id,
                'Corner plot for source frame parameters', 'pe'
            )
        ) | gracedb.create_label.si('PE_READY', superevent_id) | \
        clean_up.si(rundir)


@app.task(ignore_result=True, shared=False)
def start_pe(ini_contents, preferred_event_id, superevent_id):
    """Run LALInference on a given event.

    Parameters
    ----------
    ini_contents : str
        The content of online_pe.ini
    preferred_event_id : str
        The GraceDb ID of a target preferred event
    superevent_id : str
        The GraceDb ID of a target superevent
    """
    # make a run directory
    lalinference_dir = os.path.expanduser('~/.cache/lalinference')
    mkpath(lalinference_dir)
    rundir = tempfile.mkdtemp(dir=lalinference_dir)

    (
        dag_prepare.s(rundir, ini_contents, preferred_event_id, superevent_id)
        |
        condor.submit.s().on_error(
            job_error_notification.s(superevent_id, rundir)
        )
        |
        dag_finished(rundir, preferred_event_id, superevent_id)
    ).delay()
